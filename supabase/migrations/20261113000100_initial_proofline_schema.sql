BEGIN;

-- ============================================================
-- PROOFLINE DATABASE FOUNDATION
-- ============================================================

-- 1. ENUM TYPES

CREATE TYPE public.workspace_role AS ENUM (
    'brand_owner',
    'creator'
);

CREATE TYPE public.brand_rule_kind AS ENUM (
    'brand_voice',
    'messaging',
    'channel_guidance',
    'other'
);

CREATE TYPE public.brand_rule_state AS ENUM (
    'active',
    'inactive'
);

CREATE TYPE public.term_entry_kind AS ENUM (
    'preferred',
    'required',
    'restricted'
);

CREATE TYPE public.claim_kind AS ENUM (
    'factual',
    'promotional'
);

CREATE TYPE public.claim_passport_state AS ENUM (
    'draft',
    'active',
    'review_due',
    'retired'
);

CREATE TYPE public.passport_version_state AS ENUM (
    'draft',
    'active',
    'superseded',
    'withdrawn'
);


-- ============================================================
-- 2. WORKSPACES
-- ============================================================

CREATE TABLE public.workspaces (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    name TEXT NOT NULL
        CHECK (char_length(btrim(name)) BETWEEN 2 AND 120),

    slug TEXT NOT NULL UNIQUE
        CHECK (
            slug = lower(slug)
            AND slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$'
        ),

    created_by UUID NOT NULL
        REFERENCES auth.users(id) ON DELETE RESTRICT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);


-- ============================================================
-- 3. WORKSPACE MEMBERSHIPS AND ROLES
-- ============================================================

CREATE TABLE public.workspace_members (
    workspace_id UUID NOT NULL
        REFERENCES public.workspaces(id) ON DELETE CASCADE,

    user_id UUID NOT NULL
        REFERENCES auth.users(id) ON DELETE CASCADE,

    role public.workspace_role NOT NULL DEFAULT 'creator',

    invited_by UUID
        REFERENCES auth.users(id) ON DELETE SET NULL,

    joined_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    PRIMARY KEY (workspace_id, user_id)
);

CREATE INDEX workspace_members_user_id_idx
    ON public.workspace_members(user_id);


-- ============================================================
-- 4. BRAND RULES
-- ============================================================

CREATE TABLE public.brand_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    workspace_id UUID NOT NULL
        REFERENCES public.workspaces(id) ON DELETE CASCADE,

    rule_kind public.brand_rule_kind NOT NULL,

    title TEXT NOT NULL
        CHECK (char_length(btrim(title)) BETWEEN 2 AND 120),

    description TEXT,

    rule_text TEXT NOT NULL
        CHECK (char_length(btrim(rule_text)) > 0),

    channel TEXT,

    state public.brand_rule_state NOT NULL DEFAULT 'active',

    created_by UUID NOT NULL
        REFERENCES auth.users(id) ON DELETE RESTRICT
        DEFAULT auth.uid(),

    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (workspace_id, title)
);

CREATE INDEX brand_rules_workspace_state_idx
    ON public.brand_rules(workspace_id, state);


-- ============================================================
-- 5. TERMINOLOGY ENTRIES
-- ============================================================

CREATE TABLE public.term_entries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    workspace_id UUID NOT NULL
        REFERENCES public.workspaces(id) ON DELETE CASCADE,

    term_type public.term_entry_kind NOT NULL,

    term TEXT NOT NULL
        CHECK (
            char_length(btrim(term)) BETWEEN 1 AND 200
        ),

    preferred_replacement TEXT,

    explanation TEXT,

    case_sensitive BOOLEAN NOT NULL DEFAULT false,

    match_whole_word BOOLEAN NOT NULL DEFAULT true,

    is_active BOOLEAN NOT NULL DEFAULT true,

    created_by UUID NOT NULL
        REFERENCES auth.users(id) ON DELETE RESTRICT
        DEFAULT auth.uid(),

    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (workspace_id, term_type, term),

    CHECK (
        preferred_replacement IS NULL
        OR char_length(btrim(preferred_replacement)) > 0
    )
);

CREATE UNIQUE INDEX term_entries_unique_ci_idx
    ON public.term_entries (
        workspace_id,
        term_type,
        lower(term)
    );

CREATE INDEX term_entries_workspace_active_idx
    ON public.term_entries(workspace_id, is_active);


-- ============================================================
-- 6. CLAIM PASSPORTS
-- ============================================================

CREATE TABLE public.claim_passports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    workspace_id UUID NOT NULL
        REFERENCES public.workspaces(id) ON DELETE CASCADE,

    passport_code TEXT NOT NULL
        CHECK (
            passport_code = upper(passport_code)
            AND passport_code ~ '^[A-Z0-9][A-Z0-9._-]{0,63}$'
        ),

    subject TEXT NOT NULL
        CHECK (char_length(btrim(subject)) > 0),

    claim_type public.claim_kind NOT NULL,

    summary TEXT,

    status public.claim_passport_state NOT NULL DEFAULT 'draft',

    current_version_id UUID,

    created_by UUID NOT NULL
        REFERENCES auth.users(id) ON DELETE RESTRICT
        DEFAULT auth.uid(),

    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (workspace_id, passport_code),

    UNIQUE (id, workspace_id)
);

CREATE INDEX claim_passports_workspace_status_idx
    ON public.claim_passports(workspace_id, status);


-- ============================================================
-- 7. CLAIM PASSPORT VERSIONS AND EVIDENCE PROVENANCE
-- ============================================================

CREATE TABLE public.claim_passport_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    workspace_id UUID NOT NULL,

    claim_passport_id UUID NOT NULL,

    version_number INTEGER NOT NULL
        CHECK (version_number >= 1),

    approved_wording TEXT NOT NULL
        CHECK (char_length(btrim(approved_wording)) > 0),

    subject TEXT NOT NULL,

    attribute TEXT NOT NULL,

    permitted_value TEXT,

    numeric_value NUMERIC(20, 6),

    unit TEXT,

    qualifier TEXT,

    required_conditions TEXT,

    product_scope TEXT,

    channel_scope TEXT,

    market_scope TEXT,

    valid_from DATE,

    valid_until DATE,

    -- Evidence provenance
    evidence_source_title TEXT,

    evidence_source_url TEXT,

    evidence_reference TEXT,

    evidence_excerpt TEXT,

    evidence_source_version TEXT,

    -- Ownership and verification
    owner_id UUID NOT NULL
        REFERENCES auth.users(id) ON DELETE RESTRICT
        DEFAULT auth.uid(),

    verified_by UUID
        REFERENCES auth.users(id) ON DELETE RESTRICT,

    verified_at TIMESTAMPTZ,

    review_by DATE,

    status public.passport_version_state NOT NULL DEFAULT 'draft',

    created_by UUID NOT NULL
        REFERENCES auth.users(id) ON DELETE RESTRICT
        DEFAULT auth.uid(),

    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT passport_version_parent_fk
        FOREIGN KEY (claim_passport_id, workspace_id)
        REFERENCES public.claim_passports(id, workspace_id)
        ON DELETE CASCADE,

    UNIQUE (claim_passport_id, version_number),

    UNIQUE (id, claim_passport_id, workspace_id),

    CHECK (
        numeric_value IS NULL
        OR unit IS NOT NULL
    ),

    CHECK (
        valid_from IS NULL
        OR valid_until IS NULL
        OR valid_until >= valid_from
    ),

    CHECK (
        evidence_source_url IS NULL
        OR evidence_source_url ~* '^https?://'
    ),

    -- An active evidence record must be verifiable.
    CHECK (
        status <> 'active'
        OR (
            evidence_source_title IS NOT NULL
            AND char_length(btrim(evidence_source_title)) > 0

            AND evidence_excerpt IS NOT NULL
            AND char_length(btrim(evidence_excerpt)) > 0

            AND (
                evidence_source_url IS NOT NULL
                OR (
                    evidence_reference IS NOT NULL
                    AND char_length(btrim(evidence_reference)) > 0
                )
            )

            AND verified_by IS NOT NULL
            AND verified_at IS NOT NULL
            AND review_by IS NOT NULL
        )
    )
);

CREATE INDEX passport_versions_workspace_passport_idx
    ON public.claim_passport_versions(
        workspace_id,
        claim_passport_id,
        version_number DESC
    );


-- Ensure the current version belongs to the same Passport
-- and workspace.

ALTER TABLE public.claim_passports
    ADD CONSTRAINT claim_passports_current_version_fk
    FOREIGN KEY (
        current_version_id,
        id,
        workspace_id
    )
    REFERENCES public.claim_passport_versions(
        id,
        claim_passport_id,
        workspace_id
    )
    DEFERRABLE INITIALLY DEFERRED;


-- ============================================================
-- 8. UPDATED_AT FUNCTION
-- ============================================================

CREATE OR REPLACE FUNCTION public.set_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql
SET search_path = ''
AS $function$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$function$;


CREATE TRIGGER trg_workspaces_updated_at
BEFORE UPDATE ON public.workspaces
FOR EACH ROW
EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER trg_brand_rules_updated_at
BEFORE UPDATE ON public.brand_rules
FOR EACH ROW
EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER trg_term_entries_updated_at
BEFORE UPDATE ON public.term_entries
FOR EACH ROW
EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER trg_claim_passports_updated_at
BEFORE UPDATE ON public.claim_passports
FOR EACH ROW
EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER trg_passport_versions_updated_at
BEFORE UPDATE ON public.claim_passport_versions
FOR EACH ROW
EXECUTE FUNCTION public.set_updated_at();


-- ============================================================
-- 9. WORKSPACE ACCESS HELPER FUNCTIONS
-- ============================================================

CREATE OR REPLACE FUNCTION public.is_workspace_member(
    target_workspace_id UUID
)
RETURNS BOOLEAN
LANGUAGE SQL
STABLE
SECURITY DEFINER
SET search_path = ''
AS $function$
    SELECT EXISTS (
        SELECT 1
        FROM public.workspace_members AS wm
        WHERE wm.workspace_id = target_workspace_id
          AND wm.user_id = (SELECT auth.uid())
    );
$function$;


CREATE OR REPLACE FUNCTION public.has_workspace_role(
    target_workspace_id UUID,
    allowed_roles TEXT[]
)
RETURNS BOOLEAN
LANGUAGE SQL
STABLE
SECURITY DEFINER
SET search_path = ''
AS $function$
    SELECT EXISTS (
        SELECT 1
        FROM public.workspace_members AS wm
        WHERE wm.workspace_id = target_workspace_id
          AND wm.user_id = (SELECT auth.uid())
          AND wm.role::TEXT = ANY(allowed_roles)
    );
$function$;


-- ============================================================
-- 10. AUTOMATIC WORKSPACE OWNER MEMBERSHIP
-- ============================================================

CREATE OR REPLACE FUNCTION public.add_workspace_owner_membership()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $function$
BEGIN
    INSERT INTO public.workspace_members (
        workspace_id,
        user_id,
        role
    )
    VALUES (
        NEW.id,
        NEW.created_by,
        'brand_owner'
    );

    RETURN NEW;
END;
$function$;


CREATE TRIGGER trg_add_workspace_owner
AFTER INSERT ON public.workspaces
FOR EACH ROW
EXECUTE FUNCTION public.add_workspace_owner_membership();


-- ============================================================
-- 11. PREVENT REMOVAL OF THE LAST BRAND OWNER
-- ============================================================

CREATE OR REPLACE FUNCTION public.guard_workspace_owner_integrity()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $function$
DECLARE
    remaining_owners INTEGER;
BEGIN
    IF TG_OP = 'UPDATE'
       AND OLD.role = 'brand_owner'
       AND NEW.role <> 'brand_owner'
    THEN
        SELECT count(*)
        INTO remaining_owners
        FROM public.workspace_members
        WHERE workspace_id = OLD.workspace_id
          AND role = 'brand_owner'
          AND user_id <> OLD.user_id;

        IF remaining_owners = 0 THEN
            RAISE EXCEPTION
                'A workspace must retain at least one Brand Owner.';
        END IF;
    END IF;

    IF TG_OP = 'DELETE'
       AND OLD.role = 'brand_owner'
    THEN
        IF EXISTS (
            SELECT 1
            FROM public.workspaces
            WHERE id = OLD.workspace_id
        ) THEN
            SELECT count(*)
            INTO remaining_owners
            FROM public.workspace_members
            WHERE workspace_id = OLD.workspace_id
              AND role = 'brand_owner'
              AND user_id <> OLD.user_id;

            IF remaining_owners = 0 THEN
                RAISE EXCEPTION
                    'A workspace must retain at least one Brand Owner.';
            END IF;
        END IF;

        RETURN OLD;
    END IF;

    RETURN NEW;
END;
$function$;


CREATE TRIGGER trg_guard_workspace_owner
BEFORE UPDATE OF role OR DELETE
ON public.workspace_members
FOR EACH ROW
EXECUTE FUNCTION public.guard_workspace_owner_integrity();


-- ============================================================
-- 12. REQUIRE AN ACTIVE VERSION FOR ACTIVE PASSPORTS
-- ============================================================

CREATE OR REPLACE FUNCTION public.validate_current_passport_version()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $function$
DECLARE
    version_state TEXT;
BEGIN
    IF NEW.status IN ('active', 'review_due') THEN

        IF NEW.current_version_id IS NULL THEN
            RAISE EXCEPTION
                'An active Claim Passport must have a current version.';
        END IF;

        SELECT status::TEXT
        INTO version_state
        FROM public.claim_passport_versions
        WHERE id = NEW.current_version_id
          AND claim_passport_id = NEW.id
          AND workspace_id = NEW.workspace_id;

        IF version_state IS DISTINCT FROM 'active' THEN
            RAISE EXCEPTION
                'The current Claim Passport version must be active.';
        END IF;
    END IF;

    RETURN NEW;
END;
$function$;


CREATE TRIGGER trg_validate_current_passport_version
BEFORE INSERT OR UPDATE OF status, current_version_id
ON public.claim_passports
FOR EACH ROW
EXECUTE FUNCTION public.validate_current_passport_version();


-- ============================================================
-- 13. PROTECT CLAIM PASSPORT VERSION HISTORY
-- ============================================================

CREATE OR REPLACE FUNCTION public.guard_passport_version_immutability()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $function$
BEGIN
    IF (
        to_jsonb(NEW) - 'status' - 'updated_at'
    ) IS DISTINCT FROM (
        to_jsonb(OLD) - 'status' - 'updated_at'
    ) THEN
        RAISE EXCEPTION
            'Passport version evidence and content cannot be edited. Create a new version instead.';
    END IF;

    IF NEW.status = OLD.status THEN
        RETURN NEW;
    END IF;

    IF NOT (
        (OLD.status = 'draft'
            AND NEW.status IN ('active', 'withdrawn'))
        OR
        (OLD.status = 'active'
            AND NEW.status IN ('superseded', 'withdrawn'))
    ) THEN
        RAISE EXCEPTION
            'Invalid Claim Passport version status transition.';
    END IF;

    IF OLD.status = 'active' AND EXISTS (
        SELECT 1
        FROM public.claim_passports
        WHERE id = OLD.claim_passport_id
          AND workspace_id = OLD.workspace_id
          AND current_version_id = OLD.id
          AND status IN ('active', 'review_due')
    ) THEN
        RAISE EXCEPTION
            'Change the Passport current version before superseding its active version.';
    END IF;

    RETURN NEW;
END;
$function$;


CREATE TRIGGER trg_passport_version_immutability
BEFORE UPDATE ON public.claim_passport_versions
FOR EACH ROW
EXECUTE FUNCTION public.guard_passport_version_immutability();


-- ============================================================
-- 14. ENABLE ROW LEVEL SECURITY
-- ============================================================

ALTER TABLE public.workspaces
    ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.workspace_members
    ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.brand_rules
    ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.term_entries
    ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.claim_passports
    ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.claim_passport_versions
    ENABLE ROW LEVEL SECURITY;


-- ============================================================
-- 15. WORKSPACE POLICIES
-- ============================================================

CREATE POLICY workspaces_select_member
ON public.workspaces
FOR SELECT
TO authenticated
USING (
    (SELECT public.is_workspace_member(id))
);

CREATE POLICY workspaces_insert_owner
ON public.workspaces
FOR INSERT
TO authenticated
WITH CHECK (
    created_by = (SELECT auth.uid())
);

CREATE POLICY workspaces_update_owner
ON public.workspaces
FOR UPDATE
TO authenticated
USING (
    (SELECT public.has_workspace_role(
        id,
        ARRAY['brand_owner']
    ))
)
WITH CHECK (
    (SELECT public.has_workspace_role(
        id,
        ARRAY['brand_owner']
    ))
);


-- ============================================================
-- 16. MEMBERSHIP POLICIES
-- ============================================================

CREATE POLICY workspace_members_select_member
ON public.workspace_members
FOR SELECT
TO authenticated
USING (
    (SELECT public.is_workspace_member(workspace_id))
);

CREATE POLICY workspace_members_insert_owner
ON public.workspace_members
FOR INSERT
TO authenticated
WITH CHECK (
    (SELECT public.has_workspace_role(
        workspace_id,
        ARRAY['brand_owner']
    ))
    AND invited_by = (SELECT auth.uid())
);

CREATE POLICY workspace_members_update_owner
ON public.workspace_members
FOR UPDATE
TO authenticated
USING (
    (SELECT public.has_workspace_role(
        workspace_id,
        ARRAY['brand_owner']
    ))
)
WITH CHECK (
    (SELECT public.has_workspace_role(
        workspace_id,
        ARRAY['brand_owner']
    ))
);

CREATE POLICY workspace_members_delete_owner
ON public.workspace_members
FOR DELETE
TO authenticated
USING (
    (SELECT public.has_workspace_role(
        workspace_id,
        ARRAY['brand_owner']
    ))
);


-- ============================================================
-- 17. BRAND RULE POLICIES
-- ============================================================

CREATE POLICY brand_rules_select_member
ON public.brand_rules
FOR SELECT
TO authenticated
USING (
    (SELECT public.is_workspace_member(workspace_id))
    AND (
        state = 'active'
        OR (SELECT public.has_workspace_role(
            workspace_id,
            ARRAY['brand_owner']
        ))
    )
);

CREATE POLICY brand_rules_insert_owner
ON public.brand_rules
FOR INSERT
TO authenticated
WITH CHECK (
    (SELECT public.has_workspace_role(
        workspace_id,
        ARRAY['brand_owner']
    ))
    AND created_by = (SELECT auth.uid())
);

CREATE POLICY brand_rules_update_owner
ON public.brand_rules
FOR UPDATE
TO authenticated
USING (
    (SELECT public.has_workspace_role(
        workspace_id,
        ARRAY['brand_owner']
    ))
)
WITH CHECK (
    (SELECT public.has_workspace_role(
        workspace_id,
        ARRAY['brand_owner']
    ))
);

CREATE POLICY brand_rules_delete_owner
ON public.brand_rules
FOR DELETE
TO authenticated
USING (
    (SELECT public.has_workspace_role(
        workspace_id,
        ARRAY['brand_owner']
    ))
);


-- ============================================================
-- 18. TERMINOLOGY POLICIES
-- ============================================================

CREATE POLICY term_entries_select_member
ON public.term_entries
FOR SELECT
TO authenticated
USING (
    (SELECT public.is_workspace_member(workspace_id))
    AND (
        is_active = true
        OR (SELECT public.has_workspace_role(
            workspace_id,
            ARRAY['brand_owner']
        ))
    )
);

CREATE POLICY term_entries_insert_owner
ON public.term_entries
FOR INSERT
TO authenticated
WITH CHECK (
    (SELECT public.has_workspace_role(
        workspace_id,
        ARRAY['brand_owner']
    ))
    AND created_by = (SELECT auth.uid())
);

CREATE POLICY term_entries_update_owner
ON public.term_entries
FOR UPDATE
TO authenticated
USING (
    (SELECT public.has_workspace_role(
        workspace_id,
        ARRAY['brand_owner']
    ))
)
WITH CHECK (
    (SELECT public.has_workspace_role(
        workspace_id,
        ARRAY['brand_owner']
    ))
);

CREATE POLICY term_entries_delete_owner
ON public.term_entries
FOR DELETE
TO authenticated
USING (
    (SELECT public.has_workspace_role(
        workspace_id,
        ARRAY['brand_owner']
    ))
);


-- ============================================================
-- 19. CLAIM PASSPORT POLICIES
-- ============================================================

CREATE POLICY claim_passports_select_member
ON public.claim_passports
FOR SELECT
TO authenticated
USING (
    (SELECT public.is_workspace_member(workspace_id))
    AND (
        status IN ('active', 'review_due')
        OR (SELECT public.has_workspace_role(
            workspace_id,
            ARRAY['brand_owner']
        ))
    )
);

CREATE POLICY claim_passports_insert_owner
ON public.claim_passports
FOR INSERT
TO authenticated
WITH CHECK (
    (SELECT public.has_workspace_role(
        workspace_id,
        ARRAY['brand_owner']
    ))
    AND created_by = (SELECT auth.uid())
);

CREATE POLICY claim_passports_update_owner
ON public.claim_passports
FOR UPDATE
TO authenticated
USING (
    (SELECT public.has_workspace_role(
        workspace_id,
        ARRAY['brand_owner']
    ))
)
WITH CHECK (
    (SELECT public.has_workspace_role(
        workspace_id,
        ARRAY['brand_owner']
    ))
);


-- ============================================================
-- 20. CLAIM PASSPORT VERSION POLICIES
-- ============================================================

CREATE POLICY passport_versions_select_member
ON public.claim_passport_versions
FOR SELECT
TO authenticated
USING (
    (SELECT public.is_workspace_member(workspace_id))
    AND EXISTS (
        SELECT 1
        FROM public.claim_passports AS cp
        WHERE cp.id = claim_passport_id
          AND cp.workspace_id =
              claim_passport_versions.workspace_id
          AND (
              cp.status IN ('active', 'review_due')
              OR (SELECT public.has_workspace_role(
                  cp.workspace_id,
                  ARRAY['brand_owner']
              ))
          )
    )
);

CREATE POLICY passport_versions_insert_owner
ON public.claim_passport_versions
FOR INSERT
TO authenticated
WITH CHECK (
    (SELECT public.has_workspace_role(
        workspace_id,
        ARRAY['brand_owner']
    ))
    AND created_by = (SELECT auth.uid())
    AND owner_id = (SELECT auth.uid())
);

CREATE POLICY passport_versions_update_owner
ON public.claim_passport_versions
FOR UPDATE
TO authenticated
USING (
    (SELECT public.has_workspace_role(
        workspace_id,
        ARRAY['brand_owner']
    ))
)
WITH CHECK (
    (SELECT public.has_workspace_role(
        workspace_id,
        ARRAY['brand_owner']
    ))
);


-- ============================================================
-- 21. TABLE AND COLUMN PRIVILEGES
-- ============================================================

GRANT USAGE ON SCHEMA public TO authenticated;

GRANT USAGE ON TYPE
    public.workspace_role,
    public.brand_rule_kind,
    public.brand_rule_state,
    public.term_entry_kind,
    public.claim_kind,
    public.claim_passport_state,
    public.passport_version_state
TO authenticated;


-- Remove pre-existing API access before granting exact permissions.

REVOKE ALL ON TABLE
    public.workspaces,
    public.workspace_members,
    public.brand_rules,
    public.term_entries,
    public.claim_passports,
    public.claim_passport_versions
FROM anon, authenticated;


-- Workspaces

GRANT SELECT, INSERT, UPDATE
ON public.workspaces TO authenticated;

REVOKE UPDATE ON public.workspaces FROM authenticated;

GRANT UPDATE (name, slug)
ON public.workspaces TO authenticated;


-- Memberships

GRANT SELECT, INSERT, DELETE
ON public.workspace_members TO authenticated;

GRANT UPDATE (role)
ON public.workspace_members TO authenticated;


-- Brand rules

GRANT SELECT, INSERT, DELETE
ON public.brand_rules TO authenticated;

GRANT UPDATE (
    rule_kind,
    title,
    description,
    rule_text,
    channel,
    state
)
ON public.brand_rules TO authenticated;


-- Terminology

GRANT SELECT, INSERT, DELETE
ON public.term_entries TO authenticated;

GRANT UPDATE (
    term_type,
    term,
    preferred_replacement,
    explanation,
    case_sensitive,
    match_whole_word,
    is_active
)
ON public.term_entries TO authenticated;


-- Claim Passports

GRANT SELECT, INSERT
ON public.claim_passports TO authenticated;

GRANT UPDATE (
    passport_code,
    subject,
    claim_type,
    summary,
    status,
    current_version_id
)
ON public.claim_passports TO authenticated;


-- Passport versions
-- Evidence content is immutable after creation.
-- Only lifecycle status can be updated.

GRANT SELECT, INSERT
ON public.claim_passport_versions TO authenticated;

GRANT UPDATE (status)
ON public.claim_passport_versions TO authenticated;


-- ============================================================
-- 22. FUNCTION EXECUTION PRIVILEGES
-- ============================================================

REVOKE ALL ON FUNCTION
    public.set_updated_at()
FROM PUBLIC, anon, authenticated;

REVOKE ALL ON FUNCTION
    public.is_workspace_member(UUID)
FROM PUBLIC, anon;

REVOKE ALL ON FUNCTION
    public.has_workspace_role(UUID, TEXT[])
FROM PUBLIC, anon;

REVOKE ALL ON FUNCTION
    public.add_workspace_owner_membership()
FROM PUBLIC, anon, authenticated;

REVOKE ALL ON FUNCTION
    public.guard_workspace_owner_integrity()
FROM PUBLIC, anon, authenticated;

REVOKE ALL ON FUNCTION
    public.validate_current_passport_version()
FROM PUBLIC, anon, authenticated;

REVOKE ALL ON FUNCTION
    public.guard_passport_version_immutability()
FROM PUBLIC, anon, authenticated;


GRANT EXECUTE ON FUNCTION
    public.is_workspace_member(UUID)
TO authenticated;

GRANT EXECUTE ON FUNCTION
    public.has_workspace_role(UUID, TEXT[])
TO authenticated;


-- ============================================================
-- MIGRATION COMPLETE
-- ============================================================

COMMIT;