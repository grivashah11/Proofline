BEGIN;

-- Brand Owners can maintain concrete writing examples alongside the
-- manual Brand Voice guidance. Examples are reference material, not a score.
ALTER TABLE public.brand_rules
    ADD COLUMN IF NOT EXISTS tone_examples TEXT NOT NULL DEFAULT '';

ALTER TABLE public.brand_rules
    ADD CONSTRAINT brand_rules_tone_examples_length
    CHECK (char_length(tone_examples) <= 5000);

GRANT UPDATE (tone_examples)
ON public.brand_rules
TO authenticated;

-- A Creator can add a verbatim claim omitted by AI extraction. The database
-- deliberately records it as needs_verification: client-supplied fields can
-- never turn a manually added claim into an automatically supported claim.
CREATE OR REPLACE FUNCTION public.add_manual_claim_to_analysis(
    p_workspace_id UUID,
    p_content_id UUID,
    p_analysis_id UUID,
    p_revision_id UUID,
    p_candidate_claim JSONB,
    p_start_index INTEGER,
    p_end_index INTEGER
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
    v_finding public.analysis_findings%ROWTYPE;
    v_finding_number INTEGER;
    v_findings JSONB;
    v_exact_text TEXT;
    v_revision_text TEXT;
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

    IF p_candidate_claim IS NULL
       OR jsonb_typeof(p_candidate_claim) <> 'object'
       OR NULLIF(btrim(p_candidate_claim->>'exact_text'), '') IS NULL
       OR NULLIF(btrim(p_candidate_claim->>'subject'), '') IS NULL
       OR NULLIF(btrim(p_candidate_claim->>'attribute'), '') IS NULL
       OR p_candidate_claim->>'claim_kind' IS NULL
       OR p_candidate_claim->>'claim_kind' NOT IN ('factual', 'promotional')
       OR char_length(p_candidate_claim->>'exact_text') > 3000
       OR p_start_index IS NULL
       OR p_end_index IS NULL
       OR p_start_index < 0
       OR p_end_index <= p_start_index
    THEN
        RAISE EXCEPTION 'Invalid manual claim data.'
            USING ERRCODE = '22023';
    END IF;

    v_exact_text := p_candidate_claim->>'exact_text';

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

    IF v_content.status NOT IN ('draft', 'changes_requested') THEN
        RAISE EXCEPTION 'Manual claims can only be added to editable drafts.'
            USING ERRCODE = 'P0001';
    END IF;

    IF v_content.current_revision_id IS DISTINCT FROM p_revision_id THEN
        RAISE EXCEPTION 'The revision is no longer current.'
            USING ERRCODE = 'P0001';
    END IF;

    SELECT cr.content_text
    INTO v_revision_text
    FROM public.content_revisions AS cr
    WHERE cr.id = p_revision_id
      AND cr.content_id = p_content_id
      AND cr.workspace_id = p_workspace_id;

    IF NOT FOUND OR position(v_exact_text IN v_revision_text) = 0 THEN
        RAISE EXCEPTION 'Claim excerpt is not present in the current revision.'
            USING ERRCODE = '22023';
    END IF;

    SELECT *
    INTO v_analysis
    FROM public.analysis_runs
    WHERE id = p_analysis_id
      AND workspace_id = p_workspace_id
      AND content_id = p_content_id
      AND revision_id = p_revision_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Analysis run not found for the current revision.'
            USING ERRCODE = 'P0002';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM public.analysis_findings AS af
        WHERE af.analysis_run_id = p_analysis_id
          AND af.category = 'claim'
          AND af.candidate_claim->>'exact_text' = v_exact_text
          AND lower(af.candidate_claim->>'subject') = lower(p_candidate_claim->>'subject')
          AND lower(af.candidate_claim->>'attribute') = lower(p_candidate_claim->>'attribute')
    ) THEN
        RAISE EXCEPTION 'This claim is already present in the analysis.'
            USING ERRCODE = '23505';
    END IF;

    SELECT COALESCE(MAX(finding_number), 0) + 1
    INTO v_finding_number
    FROM public.analysis_findings
    WHERE analysis_run_id = p_analysis_id;

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
        candidate_claim
    )
    VALUES (
        p_workspace_id,
        p_analysis_id,
        p_revision_id,
        v_finding_number,
        'ai_claim',
        NULL,
        'claim',
        'needs_verification',
        'warning',
        'Manually added claim needs verification',
        'A workspace member added this claim because automated extraction may have missed it. No approved evidence has been established by this manual entry.',
        'Ask the Brand Owner to match this statement to an active Claim Passport or verify it before approval.',
        p_start_index,
        p_end_index,
        v_exact_text,
        TRUE,
        p_candidate_claim
    )
    RETURNING * INTO v_finding;

    UPDATE public.analysis_runs
    SET claim_needs_verification_count = claim_needs_verification_count + 1
    WHERE id = p_analysis_id
    RETURNING * INTO v_analysis;

    SELECT COALESCE(
        jsonb_agg(to_jsonb(af) ORDER BY af.finding_number),
        '[]'::JSONB
    )
    INTO v_findings
    FROM public.analysis_findings AS af
    WHERE af.analysis_run_id = p_analysis_id;

    RETURN jsonb_build_object(
        'analysis', to_jsonb(v_analysis),
        'findings', v_findings
    );
END;
$function$;

REVOKE ALL ON FUNCTION public.add_manual_claim_to_analysis(
    UUID, UUID, UUID, UUID, JSONB, INTEGER, INTEGER
) FROM PUBLIC, anon;

GRANT EXECUTE ON FUNCTION public.add_manual_claim_to_analysis(
    UUID, UUID, UUID, UUID, JSONB, INTEGER, INTEGER
) TO authenticated;

COMMIT;
