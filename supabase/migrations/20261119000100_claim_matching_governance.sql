-- Round 3 Improvements 2 and 3: claim match confidence, finding lifecycle,
-- revision audit context, and governance insight source records.
-- Additive only. Existing revisions, analyses, decisions, roles and RLS remain intact.

ALTER TABLE public.analysis_findings
    ADD COLUMN match_confidence NUMERIC(5,4),
    ADD COLUMN match_confidence_band TEXT,
    ADD COLUMN match_confidence_factors JSONB,
    ADD COLUMN normalized_claim JSONB,
    ADD COLUMN finding_fingerprint TEXT;

ALTER TABLE public.analysis_findings
    ADD CONSTRAINT analysis_findings_match_confidence_range
        CHECK (match_confidence IS NULL OR match_confidence BETWEEN 0 AND 1),
    ADD CONSTRAINT analysis_findings_match_confidence_band_valid
        CHECK (match_confidence_band IS NULL OR match_confidence_band IN ('high', 'moderate', 'low')),
    ADD CONSTRAINT analysis_findings_match_confidence_factors_array
        CHECK (match_confidence_factors IS NULL OR jsonb_typeof(match_confidence_factors) = 'array'),
    ADD CONSTRAINT analysis_findings_normalized_claim_object
        CHECK (normalized_claim IS NULL OR jsonb_typeof(normalized_claim) = 'object');

CREATE INDEX analysis_findings_fingerprint_idx
    ON public.analysis_findings (revision_id, finding_fingerprint)
    WHERE finding_fingerprint IS NOT NULL;

-- Stable fingerprints are generated inside PostgreSQL, not accepted from a client.
CREATE OR REPLACE FUNCTION public.set_analysis_finding_fingerprint()
RETURNS TRIGGER
LANGUAGE plpgsql
SET search_path = ''
AS $function$
DECLARE
    v_identity TEXT;
    v_subject TEXT;
    v_attribute TEXT;
    v_claim_kind TEXT;
BEGIN
    IF NEW.source IN ('terminology', 'brand_rule') THEN
        v_identity := concat_ws(
            '|',
            NEW.source::TEXT,
            NEW.category,
            COALESCE(NEW.source_id::TEXT, '')
        );
    ELSE
        v_subject := lower(regexp_replace(
            COALESCE(NEW.candidate_claim->>'subject', ''),
            '[^[:alnum:]]+', ' ', 'g'
        ));
        v_attribute := lower(regexp_replace(
            COALESCE(NEW.candidate_claim->>'attribute', ''),
            '[^[:alnum:]]+', ' ', 'g'
        ));
        v_claim_kind := COALESCE(NEW.candidate_claim->>'claim_kind', '');
        v_identity := concat_ws(
            '|',
            'claim',
            NEW.category,
            trim(regexp_replace(v_subject, '\s+', ' ', 'g')),
            trim(regexp_replace(v_attribute, '\s+', ' ', 'g')),
            v_claim_kind,
            trim(regexp_replace(lower(regexp_replace(COALESCE(NEW.candidate_claim->>'product_scope', ''), '[^[:alnum:]]+', ' ', 'g')), '\s+', ' ', 'g')),
            trim(regexp_replace(lower(regexp_replace(COALESCE(NEW.candidate_claim->>'channel_scope', ''), '[^[:alnum:]]+', ' ', 'g')), '\s+', ' ', 'g')),
            trim(regexp_replace(lower(regexp_replace(COALESCE(NEW.candidate_claim->>'market_scope', ''), '[^[:alnum:]]+', ' ', 'g')), '\s+', ' ', 'g'))
        );
    END IF;

    NEW.finding_fingerprint := md5(v_identity);
    RETURN NEW;
END;
$function$;

CREATE TRIGGER trg_analysis_findings_fingerprint
BEFORE INSERT ON public.analysis_findings
FOR EACH ROW
EXECUTE FUNCTION public.set_analysis_finding_fingerprint();

CREATE TABLE public.finding_lifecycle (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL,
    content_id UUID NOT NULL,
    fingerprint TEXT NOT NULL CHECK (char_length(fingerprint) = 32),
    source public.analysis_finding_source NOT NULL,
    category TEXT NOT NULL,
    source_id UUID,
    issue_title TEXT NOT NULL,
    claim_subject TEXT,
    claim_attribute TEXT,
    last_outcome public.analysis_finding_outcome NOT NULL,
    last_severity public.analysis_finding_severity NOT NULL,
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'resolved')),
    occurrence_count INTEGER NOT NULL DEFAULT 1 CHECK (occurrence_count >= 1),
    reappeared_count INTEGER NOT NULL DEFAULT 0 CHECK (reappeared_count >= 0),
    first_finding_id UUID REFERENCES public.analysis_findings(id) ON DELETE SET NULL,
    latest_finding_id UUID REFERENCES public.analysis_findings(id) ON DELETE SET NULL,
    first_revision_id UUID REFERENCES public.content_revisions(id) ON DELETE SET NULL,
    latest_revision_id UUID REFERENCES public.content_revisions(id) ON DELETE SET NULL,
    resolved_revision_id UUID REFERENCES public.content_revisions(id) ON DELETE SET NULL,
    first_analysis_run_id UUID REFERENCES public.analysis_runs(id) ON DELETE SET NULL,
    latest_analysis_run_id UUID REFERENCES public.analysis_runs(id) ON DELETE SET NULL,
    resolved_analysis_run_id UUID REFERENCES public.analysis_runs(id) ON DELETE SET NULL,
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at TIMESTAMPTZ,
    last_event TEXT NOT NULL DEFAULT 'opened'
        CHECK (last_event IN ('opened', 'persisted', 'resolved', 'reappeared')),
    CONSTRAINT finding_lifecycle_content_fk
        FOREIGN KEY (workspace_id, content_id)
        REFERENCES public.contents(workspace_id, id)
        ON DELETE CASCADE,
    UNIQUE (workspace_id, content_id, fingerprint)
);

CREATE INDEX finding_lifecycle_workspace_recent_idx
    ON public.finding_lifecycle (workspace_id, last_seen_at DESC);
CREATE INDEX finding_lifecycle_content_status_idx
    ON public.finding_lifecycle (workspace_id, content_id, status, last_seen_at DESC);
CREATE INDEX finding_lifecycle_pattern_idx
    ON public.finding_lifecycle (workspace_id, fingerprint, last_seen_at DESC);

CREATE TABLE public.finding_lifecycle_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL,
    content_id UUID NOT NULL,
    lifecycle_id UUID NOT NULL REFERENCES public.finding_lifecycle(id) ON DELETE CASCADE,
    finding_id UUID REFERENCES public.analysis_findings(id) ON DELETE SET NULL,
    analysis_run_id UUID REFERENCES public.analysis_runs(id) ON DELETE CASCADE,
    revision_id UUID REFERENCES public.content_revisions(id) ON DELETE SET NULL,
    event_type TEXT NOT NULL CHECK (event_type IN ('opened', 'persisted', 'resolved', 'reappeared')),
    actor_id UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    details JSONB NOT NULL DEFAULT '{}'::JSONB CHECK (jsonb_typeof(details) = 'object'),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT finding_lifecycle_events_content_fk
        FOREIGN KEY (workspace_id, content_id)
        REFERENCES public.contents(workspace_id, id)
        ON DELETE CASCADE
);

CREATE INDEX finding_lifecycle_events_thread_idx
    ON public.finding_lifecycle_events (workspace_id, lifecycle_id, created_at ASC);
CREATE INDEX finding_lifecycle_events_content_idx
    ON public.finding_lifecycle_events (workspace_id, content_id, created_at DESC);

ALTER TABLE public.finding_lifecycle ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.finding_lifecycle_events ENABLE ROW LEVEL SECURITY;

CREATE POLICY finding_lifecycle_select_member
ON public.finding_lifecycle
FOR SELECT TO authenticated
USING ((SELECT public.is_workspace_member(workspace_id)));

CREATE POLICY finding_lifecycle_events_select_member
ON public.finding_lifecycle_events
FOR SELECT TO authenticated
USING ((SELECT public.is_workspace_member(workspace_id)));

REVOKE ALL ON public.finding_lifecycle FROM anon, authenticated;
REVOKE ALL ON public.finding_lifecycle_events FROM anon, authenticated;
GRANT SELECT ON public.finding_lifecycle TO authenticated;
GRANT SELECT ON public.finding_lifecycle_events TO authenticated;

-- The analysis_runs INSERT occurs before its findings are inserted by
-- save_content_analysis. A deferred constraint trigger runs at transaction
-- completion, after all findings for that run are available.
CREATE OR REPLACE FUNCTION public.reconcile_finding_lifecycle_after_analysis()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $function$
DECLARE
    v_run public.analysis_runs%ROWTYPE;
    v_finding RECORD;
    v_thread public.finding_lifecycle%ROWTYPE;
    v_event_type TEXT;
BEGIN
    SELECT * INTO v_run
    FROM public.analysis_runs
    WHERE id = NEW.id;

    IF NOT FOUND THEN
        RETURN NULL;
    END IF;

    FOR v_finding IN
        SELECT DISTINCT ON (f.finding_fingerprint)
            f.id,
            f.workspace_id,
            f.analysis_run_id,
            f.revision_id,
            f.finding_fingerprint,
            f.source,
            f.source_id,
            f.category,
            f.outcome,
            f.severity,
            f.title,
            f.finding_number,
            f.candidate_claim
        FROM public.analysis_findings AS f
        WHERE f.analysis_run_id = v_run.id
          AND f.finding_fingerprint IS NOT NULL
          AND f.outcome <> 'supported'
        ORDER BY f.finding_fingerprint, f.finding_number
    LOOP
        INSERT INTO public.finding_lifecycle (
            workspace_id,
            content_id,
            fingerprint,
            source,
            category,
            source_id,
            issue_title,
            claim_subject,
            claim_attribute,
            last_outcome,
            last_severity,
            status,
            occurrence_count,
            reappeared_count,
            first_finding_id,
            latest_finding_id,
            first_revision_id,
            latest_revision_id,
            first_analysis_run_id,
            latest_analysis_run_id,
            first_seen_at,
            last_seen_at,
            last_event
        )
        VALUES (
            v_run.workspace_id,
            v_run.content_id,
            v_finding.finding_fingerprint,
            v_finding.source,
            v_finding.category,
            v_finding.source_id,
            v_finding.title,
            NULLIF(v_finding.candidate_claim->>'subject', ''),
            NULLIF(v_finding.candidate_claim->>'attribute', ''),
            v_finding.outcome,
            v_finding.severity,
            'open',
            1,
            0,
            v_finding.id,
            v_finding.id,
            v_run.revision_id,
            v_run.revision_id,
            v_run.id,
            v_run.id,
            now(),
            now(),
            'opened'
        )
        ON CONFLICT (workspace_id, content_id, fingerprint) DO NOTHING;

        IF FOUND THEN
            SELECT * INTO v_thread
            FROM public.finding_lifecycle
            WHERE workspace_id = v_run.workspace_id
              AND content_id = v_run.content_id
              AND fingerprint = v_finding.finding_fingerprint;
            v_event_type := 'opened';
        ELSE
            SELECT * INTO v_thread
            FROM public.finding_lifecycle
            WHERE workspace_id = v_run.workspace_id
              AND content_id = v_run.content_id
              AND fingerprint = v_finding.finding_fingerprint
            FOR UPDATE;

            IF v_thread.status = 'resolved' THEN
                v_event_type := 'reappeared';
                UPDATE public.finding_lifecycle
                SET status = 'open',
                    occurrence_count = occurrence_count + 1,
                    reappeared_count = reappeared_count + 1,
                    latest_finding_id = v_finding.id,
                    latest_revision_id = v_run.revision_id,
                    latest_analysis_run_id = v_run.id,
                    last_outcome = v_finding.outcome,
                    last_severity = v_finding.severity,
                    issue_title = v_finding.title,
                    claim_subject = NULLIF(v_finding.candidate_claim->>'subject', ''),
                    claim_attribute = NULLIF(v_finding.candidate_claim->>'attribute', ''),
                    last_seen_at = now(),
                    resolved_at = NULL,
                    resolved_revision_id = NULL,
                    resolved_analysis_run_id = NULL,
                    last_event = 'reappeared'
                WHERE id = v_thread.id
                RETURNING * INTO v_thread;
            ELSE
                v_event_type := 'persisted';
                UPDATE public.finding_lifecycle
                SET occurrence_count = occurrence_count + 1,
                    latest_finding_id = v_finding.id,
                    latest_revision_id = v_run.revision_id,
                    latest_analysis_run_id = v_run.id,
                    last_outcome = v_finding.outcome,
                    last_severity = v_finding.severity,
                    issue_title = v_finding.title,
                    claim_subject = NULLIF(v_finding.candidate_claim->>'subject', ''),
                    claim_attribute = NULLIF(v_finding.candidate_claim->>'attribute', ''),
                    last_seen_at = now(),
                    last_event = 'persisted'
                WHERE id = v_thread.id
                RETURNING * INTO v_thread;
            END IF;
        END IF;

        INSERT INTO public.finding_lifecycle_events (
            workspace_id, content_id, lifecycle_id, finding_id,
            analysis_run_id, revision_id, event_type, actor_id, details
        )
        VALUES (
            v_run.workspace_id,
            v_run.content_id,
            v_thread.id,
            v_finding.id,
            v_run.id,
            v_run.revision_id,
            v_event_type,
            v_run.created_by,
            jsonb_build_object(
                'finding_number', v_finding.finding_number,
                'title', v_finding.title,
                'outcome', v_finding.outcome,
                'severity', v_finding.severity
            )
        );
    END LOOP;

    -- A partial run cannot prove that AI-derived claim findings disappeared.
    -- Deterministic terminology/brand-rule findings can still be resolved.
    FOR v_thread IN
        SELECT fl.*
        FROM public.finding_lifecycle AS fl
        WHERE fl.workspace_id = v_run.workspace_id
          AND fl.content_id = v_run.content_id
          AND fl.status = 'open'
          AND NOT EXISTS (
              SELECT 1
              FROM public.analysis_findings AS current_finding
              WHERE current_finding.analysis_run_id = v_run.id
                AND current_finding.finding_fingerprint = fl.fingerprint
                AND current_finding.outcome <> 'supported'
          )
          AND (
              v_run.ai_extraction_status = 'completed'
              OR fl.source NOT IN ('claim_passport', 'ai_claim')
          )
        FOR UPDATE
    LOOP
        UPDATE public.finding_lifecycle
        SET status = 'resolved',
            resolved_at = now(),
            resolved_revision_id = v_run.revision_id,
            resolved_analysis_run_id = v_run.id,
            last_event = 'resolved'
        WHERE id = v_thread.id;

        INSERT INTO public.finding_lifecycle_events (
            workspace_id, content_id, lifecycle_id, finding_id,
            analysis_run_id, revision_id, event_type, actor_id, details
        )
        VALUES (
            v_run.workspace_id,
            v_run.content_id,
            v_thread.id,
            v_thread.latest_finding_id,
            v_run.id,
            v_run.revision_id,
            'resolved',
            v_run.created_by,
            jsonb_build_object(
                'previous_title', v_thread.issue_title,
                'resolved_by_analysis_run_id', v_run.id
            )
        );
    END LOOP;

    RETURN NULL;
END;
$function$;

CREATE CONSTRAINT TRIGGER trg_reconcile_finding_lifecycle_after_analysis
AFTER INSERT ON public.analysis_runs
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW
EXECUTE FUNCTION public.reconcile_finding_lifecycle_after_analysis();

-- Capture the exact revision and analysis context when the reviewer decides.
ALTER TABLE public.review_decisions
    ADD COLUMN review_context JSONB NOT NULL DEFAULT '{}'::JSONB,
    ADD CONSTRAINT review_decisions_review_context_object
        CHECK (jsonb_typeof(review_context) = 'object');

CREATE OR REPLACE FUNCTION public.capture_review_decision_context()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $function$
DECLARE
    v_context JSONB;
BEGIN
    SELECT jsonb_build_object(
        'captured_at', now(),
        'revision', jsonb_build_object(
            'revision_id', cr.id,
            'revision_number', cr.revision_number,
            'content_hash_md5', md5(cr.content_text)
        ),
        'analysis', jsonb_build_object(
            'analysis_run_id', ar.id,
            'run_number', ar.run_number,
            'status', ar.status,
            'ai_extraction_status', ar.ai_extraction_status,
            'created_at', ar.created_at,
            'rule_conflict_count', ar.rule_conflict_count,
            'rule_needs_review_count', ar.rule_needs_review_count,
            'claim_supported_count', ar.claim_supported_count,
            'claim_conflict_count', ar.claim_conflict_count,
            'claim_review_due_count', ar.claim_review_due_count,
            'claim_needs_verification_count', ar.claim_needs_verification_count
        ),
        'findings', COALESCE((
            SELECT jsonb_agg(
                jsonb_build_object(
                    'finding_id', f.id,
                    'finding_number', f.finding_number,
                    'source', f.source,
                    'category', f.category,
                    'outcome', f.outcome,
                    'severity', f.severity,
                    'title', f.title,
                    'matched_text', f.matched_text,
                    'source_span_verified', f.source_span_verified,
                    'passport_id', f.passport_id,
                    'passport_version_id', f.passport_version_id,
                    'passport_version_number', f.passport_version_number,
                    'evidence_reference', f.evidence_reference,
                    'match_confidence', f.match_confidence,
                    'match_confidence_band', f.match_confidence_band,
                    'match_confidence_factors', f.match_confidence_factors
                ) ORDER BY f.finding_number
            )
            FROM public.analysis_findings AS f
            WHERE f.workspace_id = NEW.workspace_id
              AND f.analysis_run_id = NEW.analysis_run_id
        ), '[]'::JSONB)
    )
    INTO v_context
    FROM public.content_revisions AS cr
    JOIN public.analysis_runs AS ar
      ON ar.workspace_id = cr.workspace_id
     AND ar.revision_id = cr.id
    WHERE cr.workspace_id = NEW.workspace_id
      AND cr.content_id = NEW.content_id
      AND cr.id = NEW.revision_id
      AND ar.id = NEW.analysis_run_id
      AND ar.content_id = NEW.content_id;

    IF v_context IS NULL THEN
        RAISE EXCEPTION 'Review context could not be captured for the selected revision and analysis.'
            USING ERRCODE = 'P0001';
    END IF;

    NEW.review_context := v_context;
    RETURN NEW;
END;
$function$;

CREATE TRIGGER trg_review_decisions_capture_context
BEFORE INSERT ON public.review_decisions
FOR EACH ROW
EXECUTE FUNCTION public.capture_review_decision_context();

-- Populate an audit snapshot for decisions recorded before this migration.
-- The referenced revision and analysis remain the exact pair stored on the decision.
UPDATE public.review_decisions AS rd
SET review_context = jsonb_build_object(
    'captured_at', rd.created_at,
    'revision', jsonb_build_object(
        'revision_id', cr.id,
        'revision_number', cr.revision_number,
        'content_hash_md5', md5(cr.content_text)
    ),
    'analysis', jsonb_build_object(
        'analysis_run_id', ar.id,
        'run_number', ar.run_number,
        'status', ar.status,
        'ai_extraction_status', ar.ai_extraction_status,
        'created_at', ar.created_at,
        'rule_conflict_count', ar.rule_conflict_count,
        'rule_needs_review_count', ar.rule_needs_review_count,
        'claim_supported_count', ar.claim_supported_count,
        'claim_conflict_count', ar.claim_conflict_count,
        'claim_review_due_count', ar.claim_review_due_count,
        'claim_needs_verification_count', ar.claim_needs_verification_count
    ),
    'findings', COALESCE((
        SELECT jsonb_agg(
            jsonb_build_object(
                'finding_id', f.id,
                'finding_number', f.finding_number,
                'source', f.source,
                'category', f.category,
                'outcome', f.outcome,
                'severity', f.severity,
                'title', f.title,
                'matched_text', f.matched_text,
                'source_span_verified', f.source_span_verified,
                'passport_id', f.passport_id,
                'passport_version_id', f.passport_version_id,
                'passport_version_number', f.passport_version_number,
                'evidence_reference', f.evidence_reference,
                'match_confidence', f.match_confidence,
                'match_confidence_band', f.match_confidence_band,
                'match_confidence_factors', f.match_confidence_factors
            ) ORDER BY f.finding_number
        )
        FROM public.analysis_findings AS f
        WHERE f.workspace_id = rd.workspace_id
          AND f.analysis_run_id = ar.id
    ), '[]'::JSONB)
)
FROM public.content_revisions AS cr
JOIN public.analysis_runs AS ar
  ON ar.workspace_id = cr.workspace_id
 AND ar.revision_id = cr.id
WHERE rd.review_context = '{}'::JSONB
  AND cr.workspace_id = rd.workspace_id
  AND cr.content_id = rd.content_id
  AND cr.id = rd.revision_id
  AND ar.id = rd.analysis_run_id
  AND ar.content_id = rd.content_id;

-- Replace the existing analysis RPC with the same validations and behaviour,
-- plus persistence of deterministic match metadata in the new columns.


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
            evidence_excerpt,
            match_confidence,
            match_confidence_band,
            match_confidence_factors,
            normalized_claim
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
            v_item->>'evidence_excerpt',
            NULLIF(v_item->>'match_confidence', '')::NUMERIC,
            NULLIF(v_item->>'match_confidence_band', ''),
            CASE
                WHEN v_item->'match_confidence_factors' IS NULL
                  OR v_item->'match_confidence_factors' = 'null'::JSONB THEN NULL
                ELSE v_item->'match_confidence_factors'
            END,
            CASE
                WHEN v_item->'normalized_claim' IS NULL
                  OR v_item->'normalized_claim' = 'null'::JSONB THEN NULL
                ELSE v_item->'normalized_claim'
            END
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

REVOKE ALL ON FUNCTION public.set_analysis_finding_fingerprint() FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.reconcile_finding_lifecycle_after_analysis() FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.capture_review_decision_context() FROM PUBLIC, anon, authenticated;

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
