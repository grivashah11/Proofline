
CREATE TYPE public.analysis_run_state AS ENUM (
    'completed',
    'partial'
);

CREATE TYPE public.ai_extraction_state AS ENUM (
    'completed',
    'unavailable'
);

CREATE TYPE public.analysis_finding_source AS ENUM (
    'terminology',
    'brand_rule',
    'claim_passport',
    'ai_claim'
);

CREATE TYPE public.analysis_finding_outcome AS ENUM (
    'supported',
    'conflict',
    'review_due',
    'needs_verification',
    'needs_review'
);

CREATE TYPE public.analysis_finding_severity AS ENUM (
    'error',
    'warning',
    'info'
);


CREATE TABLE public.analysis_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    workspace_id UUID NOT NULL,
    content_id UUID NOT NULL,
    revision_id UUID NOT NULL,

    run_number INTEGER NOT NULL CHECK (run_number >= 1),

    model TEXT NOT NULL CHECK (char_length(model) BETWEEN 1 AND 100),

    status public.analysis_run_state NOT NULL,
    ai_extraction_status public.ai_extraction_state NOT NULL,

    content_length INTEGER NOT NULL CHECK (content_length >= 0),
    channel TEXT,

    rule_checks_run INTEGER NOT NULL DEFAULT 0 CHECK (rule_checks_run >= 0),
    rule_passed_checks INTEGER NOT NULL DEFAULT 0 CHECK (rule_passed_checks >= 0),
    rule_conflict_count INTEGER NOT NULL DEFAULT 0 CHECK (rule_conflict_count >= 0),
    rule_needs_review_count INTEGER NOT NULL DEFAULT 0 CHECK (rule_needs_review_count >= 0),

    claim_supported_count INTEGER NOT NULL DEFAULT 0 CHECK (claim_supported_count >= 0),
    claim_conflict_count INTEGER NOT NULL DEFAULT 0 CHECK (claim_conflict_count >= 0),
    claim_review_due_count INTEGER NOT NULL DEFAULT 0 CHECK (claim_review_due_count >= 0),
    claim_needs_verification_count INTEGER NOT NULL DEFAULT 0 CHECK (claim_needs_verification_count >= 0),

    human_approval_required BOOLEAN NOT NULL DEFAULT TRUE,

    created_by UUID NOT NULL REFERENCES auth.users(id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT analysis_runs_workspace_content_fk
        FOREIGN KEY (workspace_id, content_id)
        REFERENCES public.contents(workspace_id, id)
        ON DELETE CASCADE,

    CONSTRAINT analysis_runs_workspace_revision_fk
        FOREIGN KEY (workspace_id, revision_id)
        REFERENCES public.content_revisions(workspace_id, id)
        ON DELETE CASCADE,

    UNIQUE (workspace_id, id),
    UNIQUE (content_id, revision_id, run_number),

    CHECK (
        (status = 'completed' AND ai_extraction_status = 'completed')
        OR
        (status = 'partial' AND ai_extraction_status = 'unavailable')
    )
);


CREATE TABLE public.analysis_findings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    workspace_id UUID NOT NULL,
    analysis_run_id UUID NOT NULL,
    revision_id UUID NOT NULL,

    finding_number INTEGER NOT NULL CHECK (finding_number >= 1),

    source public.analysis_finding_source NOT NULL,
    source_id UUID,

    category TEXT NOT NULL CHECK (
        category IN (
            'terminology',
            'messaging',
            'brand_voice',
            'channel_guidance',
            'claim'
        )
    ),

    outcome public.analysis_finding_outcome NOT NULL,
    severity public.analysis_finding_severity NOT NULL,

    title TEXT NOT NULL CHECK (char_length(title) BETWEEN 1 AND 300),
    message TEXT NOT NULL CHECK (char_length(message) BETWEEN 1 AND 5000),
    recommended_action TEXT NOT NULL CHECK (
        char_length(recommended_action) BETWEEN 1 AND 3000
    ),

    start_index INTEGER,
    end_index INTEGER,
    matched_text TEXT,
    source_span_verified BOOLEAN NOT NULL DEFAULT FALSE,

    candidate_claim JSONB,

    passport_id UUID,
    passport_version_id UUID,
    passport_version_number INTEGER,

    approved_wording TEXT,
    evidence_source_title TEXT,
    evidence_source_url TEXT,
    evidence_reference TEXT,
    evidence_excerpt TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT analysis_findings_workspace_run_fk
        FOREIGN KEY (workspace_id, analysis_run_id)
        REFERENCES public.analysis_runs(workspace_id, id)
        ON DELETE CASCADE,

    CONSTRAINT analysis_findings_workspace_revision_fk
        FOREIGN KEY (workspace_id, revision_id)
        REFERENCES public.content_revisions(workspace_id, id)
        ON DELETE CASCADE,

    UNIQUE (analysis_run_id, finding_number),

    CHECK (
        (start_index IS NULL AND end_index IS NULL)
        OR
        (start_index IS NOT NULL AND end_index IS NOT NULL
         AND start_index >= 0 AND end_index >= start_index)
    )
);


CREATE INDEX analysis_runs_workspace_created_idx
ON public.analysis_runs(workspace_id, created_at DESC);

CREATE INDEX analysis_runs_content_idx
ON public.analysis_runs(content_id, created_at DESC);

CREATE INDEX analysis_findings_run_idx
ON public.analysis_findings(analysis_run_id, finding_number);

CREATE INDEX analysis_findings_workspace_outcome_idx
ON public.analysis_findings(workspace_id, outcome);


ALTER TABLE public.analysis_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.analysis_findings ENABLE ROW LEVEL SECURITY;


CREATE POLICY analysis_runs_select_member
ON public.analysis_runs
FOR SELECT
TO authenticated
USING (
    (SELECT public.is_workspace_member(workspace_id))
);

CREATE POLICY analysis_findings_select_member
ON public.analysis_findings
FOR SELECT
TO authenticated
USING (
    (SELECT public.is_workspace_member(workspace_id))
);


REVOKE ALL ON public.analysis_runs FROM anon, authenticated;
REVOKE ALL ON public.analysis_findings FROM anon, authenticated;

GRANT SELECT ON public.analysis_runs TO authenticated;
GRANT SELECT ON public.analysis_findings TO authenticated;


CREATE OR REPLACE FUNCTION public.save_content_analysis(
    p_workspace_id UUID,
    p_content_id UUID,
    p_revision_id UUID,
    p_model TEXT,
    p_analysis_status public.analysis_run_state,
    p_ai_extraction_status public.ai_extraction_state,
    p_content_length INTEGER,
    p_channel TEXT,
    p_rule_checks_run INTEGER,
    p_rule_passed_checks INTEGER,
    p_rule_conflict_count INTEGER,
    p_rule_needs_review_count INTEGER,
    p_claim_supported_count INTEGER,
    p_claim_conflict_count INTEGER,
    p_claim_review_due_count INTEGER,
    p_claim_needs_verification_count INTEGER,
    p_findings JSONB
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $function$
DECLARE
    v_user_id UUID;
    v_content public.contents%ROWTYPE;
    v_analysis public.analysis_runs%ROWTYPE;
    v_item JSONB;
    v_findings JSONB;
    v_number INTEGER := 0;
    v_run_number INTEGER;
    v_source TEXT;
    v_category TEXT;
    v_outcome TEXT;
    v_severity TEXT;
BEGIN
    v_user_id := (SELECT auth.uid());

    IF v_user_id IS NULL THEN
        RAISE EXCEPTION 'Authentication required.'
            USING ERRCODE = '42501';
    END IF;

    IF NOT public.has_workspace_role(
        p_workspace_id,
        ARRAY['brand_owner', 'creator']
    ) THEN
        RAISE EXCEPTION 'Workspace access denied.'
            USING ERRCODE = '42501';
    END IF;

    IF p_model IS NULL
       OR char_length(p_model) NOT BETWEEN 1 AND 100
       OR p_content_length IS NULL
       OR p_content_length < 0
       OR p_rule_checks_run < 0
       OR p_rule_passed_checks < 0
       OR p_rule_conflict_count < 0
       OR p_rule_needs_review_count < 0
       OR p_claim_supported_count < 0
       OR p_claim_conflict_count < 0
       OR p_claim_review_due_count < 0
       OR p_claim_needs_verification_count < 0
    THEN
        RAISE EXCEPTION 'Invalid analysis metadata.'
            USING ERRCODE = '22023';
    END IF;

    IF p_findings IS NULL
       OR jsonb_typeof(p_findings) <> 'array'
       OR jsonb_array_length(p_findings) > 1500
    THEN
        RAISE EXCEPTION 'Invalid analysis findings.'
            USING ERRCODE = '22023';
    END IF;

    SELECT *
    INTO v_content
    FROM public.contents
    WHERE id = p_content_id
      AND workspace_id = p_workspace_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Content not found.'
            USING ERRCODE = 'P0002';
    END IF;

    IF v_content.status = 'archived' THEN
        RAISE EXCEPTION 'Archived content cannot be analysed.'
            USING ERRCODE = 'P0001';
    END IF;

    IF v_content.current_revision_id IS DISTINCT FROM p_revision_id THEN
        RAISE EXCEPTION 'The revision is no longer current. Analyse the latest revision.'
            USING ERRCODE = 'P0001';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM public.content_revisions
        WHERE id = p_revision_id
          AND content_id = p_content_id
          AND workspace_id = p_workspace_id
    ) THEN
        RAISE EXCEPTION 'Content revision not found.'
            USING ERRCODE = 'P0002';
    END IF;

    SELECT COALESCE(MAX(run_number), 0) + 1
    INTO v_run_number
    FROM public.analysis_runs
    WHERE content_id = p_content_id
      AND revision_id = p_revision_id;

    INSERT INTO public.analysis_runs (
        workspace_id,
        content_id,
        revision_id,
        run_number,
        model,
        status,
        ai_extraction_status,
        content_length,
        channel,
        rule_checks_run,
        rule_passed_checks,
        rule_conflict_count,
        rule_needs_review_count,
        claim_supported_count,
        claim_conflict_count,
        claim_review_due_count,
        claim_needs_verification_count,
        human_approval_required,
        created_by
    )
    VALUES (
        p_workspace_id,
        p_content_id,
        p_revision_id,
        v_run_number,
        p_model,
        p_analysis_status,
        p_ai_extraction_status,
        p_content_length,
        p_channel,
        p_rule_checks_run,
        p_rule_passed_checks,
        p_rule_conflict_count,
        p_rule_needs_review_count,
        p_claim_supported_count,
        p_claim_conflict_count,
        p_claim_review_due_count,
        p_claim_needs_verification_count,
        TRUE,
        v_user_id
    )
    RETURNING * INTO v_analysis;

    FOR v_item IN
        SELECT value FROM jsonb_array_elements(p_findings)
    LOOP
        v_number := v_number + 1;

        IF jsonb_typeof(v_item) <> 'object' THEN
            RAISE EXCEPTION 'Invalid finding record.'
                USING ERRCODE = '22023';
        END IF;

        v_source := v_item->>'source';
        v_category := v_item->>'category';
        v_outcome := v_item->>'outcome';
        v_severity := v_item->>'severity';

        IF v_source IS NULL OR v_source NOT IN (
            'terminology', 'brand_rule', 'claim_passport', 'ai_claim'
        ) THEN
            RAISE EXCEPTION 'Invalid finding source.'
                USING ERRCODE = '22023';
        END IF;

        IF v_category IS NULL OR v_category NOT IN (
            'terminology', 'messaging', 'brand_voice',
            'channel_guidance', 'claim'
        ) THEN
            RAISE EXCEPTION 'Invalid finding category.'
                USING ERRCODE = '22023';
        END IF;

        IF v_outcome IS NULL OR v_outcome NOT IN (
            'supported', 'conflict', 'review_due',
            'needs_verification', 'needs_review'
        ) THEN
            RAISE EXCEPTION 'Invalid finding outcome.'
                USING ERRCODE = '22023';
        END IF;

        IF v_severity IS NULL OR v_severity NOT IN (
            'error', 'warning', 'info'
        ) THEN
            RAISE EXCEPTION 'Invalid finding severity.'
                USING ERRCODE = '22023';
        END IF;

        IF NULLIF(btrim(v_item->>'title'), '') IS NULL
           OR NULLIF(btrim(v_item->>'message'), '') IS NULL
           OR NULLIF(btrim(v_item->>'recommended_action'), '') IS NULL
        THEN
            RAISE EXCEPTION 'Finding title, message and action are required.'
                USING ERRCODE = '22023';
        END IF;

        IF (v_item->>'start_index' IS NULL)
           <> (v_item->>'end_index' IS NULL)
        THEN
            RAISE EXCEPTION 'Finding text span is incomplete.'
                USING ERRCODE = '22023';
        END IF;

        INSERT INTO public.analysis_findings (
            workspace_id,
            analysis_run_id,
            revision_id,
            finding_number,
            source,
            source_id,
            category,
            outcome,
            severity,
            title,
            message,
            recommended_action,
            start_index,
            end_index,
            matched_text,
            source_span_verified,
            candidate_claim,
            passport_id,
            passport_version_id,
            passport_version_number,
            approved_wording,
            evidence_source_title,
            evidence_source_url,
            evidence_reference,
            evidence_excerpt
        )
        VALUES (
            p_workspace_id,
            v_analysis.id,
            p_revision_id,
            v_number,
            v_source::public.analysis_finding_source,
            NULLIF(v_item->>'source_id', '')::UUID,
            v_category,
            v_outcome::public.analysis_finding_outcome,
            v_severity::public.analysis_finding_severity,
            v_item->>'title',
            v_item->>'message',
            v_item->>'recommended_action',
            NULLIF(v_item->>'start_index', '')::INTEGER,
            NULLIF(v_item->>'end_index', '')::INTEGER,
            v_item->>'matched_text',
            COALESCE((v_item->>'source_span_verified')::BOOLEAN, FALSE),
            CASE
                WHEN v_item->'candidate_claim' = 'null'::JSONB THEN NULL
                ELSE v_item->'candidate_claim'
            END,
            NULLIF(v_item->>'passport_id', '')::UUID,
            NULLIF(v_item->>'passport_version_id', '')::UUID,
            NULLIF(v_item->>'passport_version_number', '')::INTEGER,
            v_item->>'approved_wording',
            v_item->>'evidence_source_title',
            v_item->>'evidence_source_url',
            v_item->>'evidence_reference',
            v_item->>'evidence_excerpt'
        );
    END LOOP;

    SELECT COALESCE(
        jsonb_agg(to_jsonb(f) ORDER BY f.finding_number),
        '[]'::JSONB
    )
    INTO v_findings
    FROM public.analysis_findings AS f
    WHERE f.analysis_run_id = v_analysis.id;

    RETURN jsonb_build_object(
        'analysis', to_jsonb(v_analysis),
        'findings', v_findings
    );
END;
$function$;


REVOKE ALL ON FUNCTION public.save_content_analysis(
    UUID, UUID, UUID, TEXT,
    public.analysis_run_state,
    public.ai_extraction_state,
    INTEGER, TEXT,
    INTEGER, INTEGER, INTEGER, INTEGER,
    INTEGER, INTEGER, INTEGER, INTEGER,
    JSONB
) FROM PUBLIC, anon, authenticated;

GRANT EXECUTE ON FUNCTION public.save_content_analysis(
    UUID, UUID, UUID, TEXT,
    public.analysis_run_state,
    public.ai_extraction_state,
    INTEGER, TEXT,
    INTEGER, INTEGER, INTEGER, INTEGER,
    INTEGER, INTEGER, INTEGER, INTEGER,
    JSONB
) TO authenticated;
