BEGIN;

-- ============================================================
-- 1. PROTECT VERSION INSERTION
-- All newly created versions must start as drafts.
-- ============================================================

CREATE OR REPLACE FUNCTION public.reject_non_draft_passport_insert()
RETURNS TRIGGER
LANGUAGE plpgsql
SET search_path = ''
AS $function$
BEGIN
    IF NEW.status <> 'draft'
       OR NEW.verified_by IS NOT NULL
       OR NEW.verified_at IS NOT NULL
    THEN
        RAISE EXCEPTION
            'New Claim Passport versions must be unverified drafts.';
    END IF;

    RETURN NEW;
END;
$function$;

CREATE TRIGGER trg_reject_non_draft_passport_insert
BEFORE INSERT ON public.claim_passport_versions
FOR EACH ROW
EXECUTE FUNCTION public.reject_non_draft_passport_insert();


-- ============================================================
-- 2. PROTECT PASSPORT VERSION IMMUTABILITY
-- ============================================================

CREATE OR REPLACE FUNCTION public.guard_passport_version_immutability()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $function$
BEGIN
    IF OLD.status = 'draft' AND NEW.status = 'active' THEN

        IF (
            to_jsonb(NEW)
            - 'status'
            - 'updated_at'
            - 'verified_by'
            - 'verified_at'
        ) IS DISTINCT FROM (
            to_jsonb(OLD)
            - 'status'
            - 'updated_at'
            - 'verified_by'
            - 'verified_at'
        ) THEN
            RAISE EXCEPTION
                'Passport evidence cannot be changed during activation.';
        END IF;

    ELSE

        IF (
            to_jsonb(NEW) - 'status' - 'updated_at'
        ) IS DISTINCT FROM (
            to_jsonb(OLD) - 'status' - 'updated_at'
        ) THEN
            RAISE EXCEPTION
                'Passport version evidence is immutable. Create a new version.';
        END IF;

    END IF;

    IF NEW.status = OLD.status THEN
        RETURN NEW;
    END IF;

    IF NOT (
        (
            OLD.status = 'draft'
            AND NEW.status IN ('active', 'withdrawn')
        )
        OR
        (
            OLD.status = 'active'
            AND NEW.status IN ('superseded', 'withdrawn')
        )
    ) THEN
        RAISE EXCEPTION
            'Invalid Claim Passport version status transition.';
    END IF;

    IF OLD.status = 'active'
       AND EXISTS (
           SELECT 1
           FROM public.claim_passports
           WHERE id = OLD.claim_passport_id
             AND workspace_id = OLD.workspace_id
             AND current_version_id = OLD.id
             AND status IN ('active', 'review_due')
       )
    THEN
        RAISE EXCEPTION
            'Change the Passport current version before superseding its active version.';
    END IF;

    RETURN NEW;
END;
$function$;


-- ============================================================
-- 3. REMOVE DIRECT VERSION UPDATE PERMISSIONS
-- Only the controlled activation RPC may update versions.
-- ============================================================

REVOKE UPDATE ON TABLE
    public.claim_passport_versions
FROM authenticated;

REVOKE UPDATE (
    status,
    verified_by,
    verified_at
)
ON TABLE public.claim_passport_versions
FROM authenticated;


-- ============================================================
-- 4. ATOMIC PASSPORT VERSION ACTIVATION
-- SECURITY DEFINER is necessary because direct UPDATE
-- permissions are deliberately removed from authenticated.
-- Explicit workspace authorization remains mandatory.
-- ============================================================

CREATE OR REPLACE FUNCTION public.activate_claim_passport_version(
    p_claim_passport_id UUID,
    p_version_id UUID
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $function$

DECLARE
    v_passport public.claim_passports%ROWTYPE;
    v_version public.claim_passport_versions%ROWTYPE;
    v_old_version_id UUID;

BEGIN

    IF auth.uid() IS NULL THEN
        RAISE EXCEPTION 'Authentication required.'
            USING ERRCODE = '42501';
    END IF;

    SELECT *
    INTO v_passport
    FROM public.claim_passports
    WHERE id = p_claim_passport_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Claim Passport not found.'
            USING ERRCODE = 'P0002';
    END IF;

    IF NOT public.has_workspace_role(
        v_passport.workspace_id,
        ARRAY['brand_owner']
    ) THEN
        RAISE EXCEPTION 'Brand Owner permission required.'
            USING ERRCODE = '42501';
    END IF;

    IF v_passport.status = 'retired' THEN
        RAISE EXCEPTION 'A retired Passport cannot be activated.'
            USING ERRCODE = 'P0001';
    END IF;

    SELECT *
    INTO v_version
    FROM public.claim_passport_versions
    WHERE id = p_version_id
      AND claim_passport_id = p_claim_passport_id
      AND workspace_id = v_passport.workspace_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Claim Passport version not found.'
            USING ERRCODE = 'P0002';
    END IF;

    IF v_version.status <> 'draft' THEN
        RAISE EXCEPTION 'Only draft versions can be activated.'
            USING ERRCODE = 'P0001';
    END IF;

    IF v_version.review_by IS NULL
       OR v_version.review_by < CURRENT_DATE
    THEN
        RAISE EXCEPTION
            'A valid future review date is required.'
            USING ERRCODE = '23514';
    END IF;

    IF v_version.valid_from IS NOT NULL
       AND v_version.valid_from > CURRENT_DATE
    THEN
        RAISE EXCEPTION
            'A future-dated version cannot be activated yet.'
            USING ERRCODE = '23514';
    END IF;

    IF v_version.valid_until IS NOT NULL
       AND v_version.valid_until < CURRENT_DATE
    THEN
        RAISE EXCEPTION
            'An expired version cannot be activated.'
            USING ERRCODE = '23514';
    END IF;

    v_old_version_id := v_passport.current_version_id;

    -- Record the authenticated human verifier.

    UPDATE public.claim_passport_versions
    SET
        status = 'active',
        verified_by = auth.uid(),
        verified_at = now()
    WHERE id = p_version_id;

    -- Move the Passport pointer to the new active version.

    UPDATE public.claim_passports
    SET
        current_version_id = p_version_id,
        status = 'active'
    WHERE id = p_claim_passport_id;

    -- Supersede the previous version only after the pointer
    -- has successfully moved.

    IF v_old_version_id IS NOT NULL
       AND v_old_version_id <> p_version_id
    THEN
        UPDATE public.claim_passport_versions
        SET status = 'superseded'
        WHERE id = v_old_version_id
          AND status = 'active';
    END IF;

    RETURN (
        SELECT to_jsonb(cp)
        FROM public.claim_passports AS cp
        WHERE cp.id = p_claim_passport_id
    );

END;
$function$;


-- ============================================================
-- 5. FUNCTION PERMISSIONS
-- ============================================================

REVOKE ALL ON FUNCTION
    public.activate_claim_passport_version(UUID, UUID)
FROM PUBLIC, anon;

GRANT EXECUTE ON FUNCTION
    public.activate_claim_passport_version(UUID, UUID)
TO authenticated;


COMMIT;