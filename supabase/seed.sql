-- ============================================================
-- PROOFLINE DEVELOPMENT SEED DATA
-- Fictional demonstration content only.
-- Safe to run repeatedly.
-- ============================================================

DO $seed$
DECLARE
    v_user_id UUID;
    v_workspace_id UUID;
    v_passport_id UUID;
    v_version_id UUID;
BEGIN

    -- Use the first registered application user for the
    -- development demo workspace.

    SELECT id
    INTO v_user_id
    FROM auth.users
    ORDER BY created_at ASC
    LIMIT 1;

    IF v_user_id IS NULL THEN
        RAISE NOTICE
            'Skipping demo seed: create an application user first.';
        RETURN;
    END IF;


    -- Create the demo workspace.

    INSERT INTO public.workspaces (
        name,
        slug,
        created_by
    )
    VALUES (
        'Proofline Demo Workspace',
        'proofline-demo',
        v_user_id
    )
    ON CONFLICT (slug) DO NOTHING
    RETURNING id INTO v_workspace_id;


    -- If it already exists, only use it when the seed user
    -- is already a member.

    IF v_workspace_id IS NULL THEN

        SELECT w.id
        INTO v_workspace_id
        FROM public.workspaces AS w
        INNER JOIN public.workspace_members AS wm
            ON wm.workspace_id = w.id
        WHERE w.slug = 'proofline-demo'
          AND wm.user_id = v_user_id
        LIMIT 1;

    END IF;


    IF v_workspace_id IS NULL THEN
        RAISE NOTICE
            'Skipping demo seed: existing demo workspace belongs to another user.';
        RETURN;
    END IF;


    -- ========================================================
    -- BRAND RULES
    -- ========================================================

    INSERT INTO public.brand_rules (
        workspace_id,
        rule_kind,
        title,
        description,
        rule_text,
        channel,
        state,
        created_by
    )
    VALUES
    (
        v_workspace_id,
        'brand_voice',
        'Brand Voice',
        'The standard communication tone.',
        'Use warm, direct and confident language. Avoid exaggerated promises.',
        NULL,
        'active',
        v_user_id
    ),
    (
        v_workspace_id,
        'messaging',
        'Evidence First',
        'Promotional claims must be supported by approved evidence.',
        'Do not publish factual or promotional claims without appropriate approved evidence.',
        NULL,
        'active',
        v_user_id
    ),
    (
        v_workspace_id,
        'channel_guidance',
        'Social Media Guidance',
        'Guidelines for social media captions.',
        'Keep social media messaging clear, concise and consistent with approved brand terminology.',
        'social',
        'active',
        v_user_id
    )
    ON CONFLICT DO NOTHING;


    -- ========================================================
    -- TERMINOLOGY
    -- ========================================================

    INSERT INTO public.term_entries (
        workspace_id,
        term_type,
        term,
        preferred_replacement,
        explanation,
        case_sensitive,
        match_whole_word,
        is_active,
        created_by
    )
    VALUES
    (
        v_workspace_id,
        'preferred',
        'HydraLite Bottle',
        NULL,
        'Use the approved product name.',
        false,
        true,
        true,
        v_user_id
    ),
    (
        v_workspace_id,
        'required',
        'Terms and conditions apply',
        NULL,
        'Required disclaimer wording for applicable promotional content.',
        false,
        true,
        true,
        v_user_id
    ),
    (
        v_workspace_id,
        'restricted',
        'guaranteed results',
        'results under stated test conditions',
        'Avoid unqualified performance guarantees.',
        false,
        false,
        true,
        v_user_id
    )
    ON CONFLICT DO NOTHING;


    -- ========================================================
    -- DEMO CLAIM PASSPORT
    -- ========================================================

    INSERT INTO public.claim_passports (
        workspace_id,
        passport_code,
        subject,
        claim_type,
        summary,
        status,
        created_by
    )
    VALUES (
        v_workspace_id,
        'PFL-DEMO-001',
        'HydraLite Bottle',
        'promotional',
        'Fictional demonstration claim about beverage temperature retention.',
        'draft',
        v_user_id
    )
    ON CONFLICT (workspace_id, passport_code) DO NOTHING;


    SELECT id
    INTO v_passport_id
    FROM public.claim_passports
    WHERE workspace_id = v_workspace_id
      AND passport_code = 'PFL-DEMO-001';


    -- ========================================================
    -- EVIDENCE-BACKED PASSPORT VERSION 1
    -- ========================================================

    INSERT INTO public.claim_passport_versions (
        workspace_id,
        claim_passport_id,
        version_number,
        approved_wording,
        subject,
        attribute,
        permitted_value,
        numeric_value,
        unit,
        qualifier,
        required_conditions,
        product_scope,
        channel_scope,
        market_scope,
        evidence_source_title,
        evidence_source_url,
        evidence_reference,
        evidence_excerpt,
        evidence_source_version,
        owner_id,
        verified_by,
        verified_at,
        review_by,
        status,
        created_by
    )
    VALUES (
        v_workspace_id,
        v_passport_id,
        1,
        'The HydraLite Bottle keeps beverages cold for up to 24 hours under the stated test conditions.',
        'HydraLite Bottle',
        'Cold temperature retention',
        '24',
        24,
        'hours',
        'up to',
        'Only applicable under the stated fictional demonstration test conditions.',
        'HydraLite Bottle',
        'social',
        'demo market',
        'Fictional Proofline Demo Test Report',
        NULL,
        'Section 2.1 - Synthetic demonstration evidence',
        'DEMO ONLY: This is fictional evidence created for the Proofline hackathon demonstration. It is not a real product test or verified commercial claim.',
        'Demo Report Version 1',
        v_user_id,
        v_user_id,
        now(),
        current_date + 365,
        'active',
        v_user_id
    )
    ON CONFLICT (claim_passport_id, version_number) DO NOTHING;


    SELECT id
    INTO v_version_id
    FROM public.claim_passport_versions
    WHERE claim_passport_id = v_passport_id
      AND version_number = 1;


    -- Activate the Passport only after its evidence version exists.

    UPDATE public.claim_passports
    SET
        current_version_id = v_version_id,
        status = 'active'
    WHERE id = v_passport_id
      AND status = 'draft'
      AND current_version_id IS NULL;


    RAISE NOTICE
        'Proofline development demo data created successfully.';

END;
$seed$;