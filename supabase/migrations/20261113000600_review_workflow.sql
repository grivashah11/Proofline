
CREATE TYPE public.review_decision_kind AS ENUM (
    'approved',
    'changes_requested',
    'rejected'
);

ALTER TABLE public.contents
ADD COLUMN submitted_analysis_run_id UUID;

ALTER TABLE public.contents
ADD CONSTRAINT contents_submitted_analysis_fk
FOREIGN KEY (workspace_id, submitted_analysis_run_id)
REFERENCES public.analysis_runs(workspace_id, id)
ON DELETE RESTRICT;


CREATE TABLE public.content_comments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    workspace_id UUID NOT NULL,
    content_id UUID NOT NULL,
    revision_id UUID NOT NULL,

    body TEXT NOT NULL
        CHECK (char_length(btrim(body)) BETWEEN 1 AND 5000),

    created_by UUID NOT NULL
        REFERENCES auth.users(id) ON DELETE RESTRICT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT content_comments_content_fk
        FOREIGN KEY (workspace_id, content_id)
        REFERENCES public.contents(workspace_id, id)
        ON DELETE CASCADE,

    CONSTRAINT content_comments_revision_fk
        FOREIGN KEY (workspace_id, revision_id)
        REFERENCES public.content_revisions(workspace_id, id)
        ON DELETE CASCADE,

    UNIQUE (workspace_id, id)
);


CREATE TABLE public.review_decisions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    workspace_id UUID NOT NULL,
    content_id UUID NOT NULL,
    revision_id UUID NOT NULL,
    analysis_run_id UUID NOT NULL,

    decision public.review_decision_kind NOT NULL,
    reviewer_comment TEXT
        CHECK (
            reviewer_comment IS NULL
            OR char_length(reviewer_comment) <= 5000
        ),

    reviewer_id UUID NOT NULL
        REFERENCES auth.users(id) ON DELETE RESTRICT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT review_decisions_content_fk
        FOREIGN KEY (workspace_id, content_id)
        REFERENCES public.contents(workspace_id, id)
        ON DELETE CASCADE,

    CONSTRAINT review_decisions_revision_fk
        FOREIGN KEY (workspace_id, revision_id)
        REFERENCES public.content_revisions(workspace_id, id)
        ON DELETE CASCADE,

    CONSTRAINT review_decisions_analysis_fk
        FOREIGN KEY (workspace_id, analysis_run_id)
        REFERENCES public.analysis_runs(workspace_id, id)
        ON DELETE RESTRICT,

    UNIQUE (content_id, revision_id),
    UNIQUE (workspace_id, id)
);


CREATE TABLE public.audit_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    workspace_id UUID NOT NULL,
    content_id UUID NOT NULL,
    revision_id UUID,

    event_type TEXT NOT NULL CHECK (
        event_type IN (
            'revision_created',
            'submitted_for_review',
            'comment_added',
            'review_decision_recorded'
        )
    ),

    actor_id UUID NOT NULL
        REFERENCES auth.users(id) ON DELETE RESTRICT,

    details JSONB NOT NULL DEFAULT '{}'::JSONB
        CHECK (jsonb_typeof(details) = 'object'),

    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT audit_events_content_fk
        FOREIGN KEY (workspace_id, content_id)
        REFERENCES public.contents(workspace_id, id)
        ON DELETE CASCADE,

    CONSTRAINT audit_events_revision_fk
        FOREIGN KEY (workspace_id, revision_id)
        REFERENCES public.content_revisions(workspace_id, id)
        ON DELETE RESTRICT,

    UNIQUE (workspace_id, id)
);


CREATE INDEX content_comments_revision_idx
ON public.content_comments(workspace_id, content_id, revision_id, created_at);

CREATE INDEX review_decisions_content_idx
ON public.review_decisions(workspace_id, content_id, created_at DESC);

CREATE INDEX audit_events_content_idx
ON public.audit_events(workspace_id, content_id, created_at DESC);


ALTER TABLE public.content_comments ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.review_decisions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.audit_events ENABLE ROW LEVEL SECURITY;

CREATE POLICY content_comments_select_member
ON public.content_comments
FOR SELECT
TO authenticated
USING (
    (SELECT public.is_workspace_member(workspace_id))
);

CREATE POLICY review_decisions_select_member
ON public.review_decisions
FOR SELECT
TO authenticated
USING (
    (SELECT public.is_workspace_member(workspace_id))
);

CREATE POLICY audit_events_select_member
ON public.audit_events
FOR SELECT
TO authenticated
USING (
    (SELECT public.is_workspace_member(workspace_id))
);

REVOKE ALL ON public.content_comments FROM anon, authenticated;
REVOKE ALL ON public.review_decisions FROM anon, authenticated;
REVOKE ALL ON public.audit_events FROM anon, authenticated;

GRANT SELECT ON public.content_comments TO authenticated;
GRANT SELECT ON public.review_decisions TO authenticated;
GRANT SELECT ON public.audit_events TO authenticated;


CREATE OR REPLACE FUNCTION public.record_content_revision_event()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $function$
BEGIN
    UPDATE public.contents
    SET
        status = 'draft',
        submitted_analysis_run_id = NULL
    WHERE id = NEW.content_id
      AND workspace_id = NEW.workspace_id;

    INSERT INTO public.audit_events (
        workspace_id,
        content_id,
        revision_id,
        event_type,
        actor_id,
        details
    )
    VALUES (
        NEW.workspace_id,
        NEW.content_id,
        NEW.id,
        'revision_created',
        NEW.created_by,
        jsonb_build_object(
            'revision_number', NEW.revision_number
        )
    );

    RETURN NEW;
END;
$function$;


CREATE TRIGGER trg_content_revision_event
AFTER INSERT ON public.content_revisions
FOR EACH ROW
EXECUTE FUNCTION public.record_content_revision_event();


CREATE OR REPLACE FUNCTION public.submit_content_for_review(
    p_workspace_id UUID,
    p_content_id UUID
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

    IF v_content.status <> 'draft' THEN
        RAISE EXCEPTION 'Only draft content can be submitted for review.'
            USING ERRCODE = 'P0001';
    END IF;

    IF v_content.current_revision_id IS NULL THEN
        RAISE EXCEPTION 'Content has no current revision.'
            USING ERRCODE = 'P0001';
    END IF;

    SELECT *
    INTO v_analysis
    FROM public.analysis_runs
    WHERE workspace_id = p_workspace_id
      AND content_id = p_content_id
      AND revision_id = v_content.current_revision_id
    ORDER BY run_number DESC
    LIMIT 1;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Run analysis on the current revision before submission.'
            USING ERRCODE = 'P0001';
    END IF;

    UPDATE public.contents
    SET
        status = 'in_review',
        submitted_analysis_run_id = v_analysis.id
    WHERE id = p_content_id
    RETURNING * INTO v_content;

    INSERT INTO public.audit_events (
        workspace_id,
        content_id,
        revision_id,
        event_type,
        actor_id,
        details
    )
    VALUES (
        p_workspace_id,
        p_content_id,
        v_content.current_revision_id,
        'submitted_for_review',
        v_user_id,
        jsonb_build_object(
            'analysis_run_id', v_analysis.id,
            'analysis_status', v_analysis.status,
            'ai_extraction_status', v_analysis.ai_extraction_status
        )
    );

    RETURN jsonb_build_object(
        'content', to_jsonb(v_content),
        'analysis_run_id', v_analysis.id,
        'analysis_status', v_analysis.status
    );
END;
$function$;


CREATE OR REPLACE FUNCTION public.add_content_comment(
    p_workspace_id UUID,
    p_content_id UUID,
    p_revision_id UUID,
    p_body TEXT
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $function$
DECLARE
    v_user_id UUID;
    v_comment public.content_comments%ROWTYPE;
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

    IF p_body IS NULL
       OR char_length(btrim(p_body)) NOT BETWEEN 1 AND 5000
    THEN
        RAISE EXCEPTION 'Invalid comment.'
            USING ERRCODE = '22023';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM public.contents
        WHERE id = p_content_id
          AND workspace_id = p_workspace_id
    ) THEN
        RAISE EXCEPTION 'Content not found.'
            USING ERRCODE = 'P0002';
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

    INSERT INTO public.content_comments (
        workspace_id,
        content_id,
        revision_id,
        body,
        created_by
    )
    VALUES (
        p_workspace_id,
        p_content_id,
        p_revision_id,
        btrim(p_body),
        v_user_id
    )
    RETURNING * INTO v_comment;

    INSERT INTO public.audit_events (
        workspace_id,
        content_id,
        revision_id,
        event_type,
        actor_id,
        details
    )
    VALUES (
        p_workspace_id,
        p_content_id,
        p_revision_id,
        'comment_added',
        v_user_id,
        jsonb_build_object(
            'comment_id', v_comment.id
        )
    );

    RETURN to_jsonb(v_comment);
END;
$function$;


CREATE OR REPLACE FUNCTION public.record_content_review_decision(
    p_workspace_id UUID,
    p_content_id UUID,
    p_decision public.review_decision_kind,
    p_reviewer_comment TEXT DEFAULT NULL
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $function$
DECLARE
    v_user_id UUID;
    v_content public.contents%ROWTYPE;
    v_review public.review_decisions%ROWTYPE;
    v_new_status public.content_status;
BEGIN
    v_user_id := (SELECT auth.uid());

    IF v_user_id IS NULL THEN
        RAISE EXCEPTION 'Authentication required.'
            USING ERRCODE = '42501';
    END IF;

    IF NOT public.has_workspace_role(
        p_workspace_id,
        ARRAY['brand_owner']
    ) THEN
        RAISE EXCEPTION 'Brand Owner permission required.'
            USING ERRCODE = '42501';
    END IF;

    IF p_reviewer_comment IS NOT NULL
       AND char_length(p_reviewer_comment) > 5000
    THEN
        RAISE EXCEPTION 'Reviewer comment is too long.'
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

    IF v_content.status <> 'in_review'
       OR v_content.submitted_analysis_run_id IS NULL
    THEN
        RAISE EXCEPTION 'Content is not awaiting reviewer decision.'
            USING ERRCODE = 'P0001';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM public.analysis_runs
        WHERE id = v_content.submitted_analysis_run_id
          AND workspace_id = p_workspace_id
          AND content_id = p_content_id
          AND revision_id = v_content.current_revision_id
    ) THEN
        RAISE EXCEPTION 'The submitted analysis does not match the current revision.'
            USING ERRCODE = 'P0001';
    END IF;

    v_new_status := CASE p_decision
        WHEN 'approved' THEN 'approved'::public.content_status
        WHEN 'changes_requested' THEN 'changes_requested'::public.content_status
        WHEN 'rejected' THEN 'rejected'::public.content_status
    END;

    INSERT INTO public.review_decisions (
        workspace_id,
        content_id,
        revision_id,
        analysis_run_id,
        decision,
        reviewer_comment,
        reviewer_id
    )
    VALUES (
        p_workspace_id,
        p_content_id,
        v_content.current_revision_id,
        v_content.submitted_analysis_run_id,
        p_decision,
        NULLIF(btrim(p_reviewer_comment), ''),
        v_user_id
    )
    RETURNING * INTO v_review;

    UPDATE public.contents
    SET status = v_new_status
    WHERE id = p_content_id
    RETURNING * INTO v_content;

    INSERT INTO public.audit_events (
        workspace_id,
        content_id,
        revision_id,
        event_type,
        actor_id,
        details
    )
    VALUES (
        p_workspace_id,
        p_content_id,
        v_content.current_revision_id,
        'review_decision_recorded',
        v_user_id,
        jsonb_build_object(
            'review_decision_id', v_review.id,
            'decision', v_review.decision,
            'analysis_run_id', v_review.analysis_run_id
        )
    );

    RETURN jsonb_build_object(
        'content', to_jsonb(v_content),
        'decision', to_jsonb(v_review)
    );
END;
$function$;


REVOKE ALL ON FUNCTION public.submit_content_for_review(UUID, UUID)
FROM PUBLIC, anon, authenticated;

REVOKE ALL ON FUNCTION public.add_content_comment(UUID, UUID, UUID, TEXT)
FROM PUBLIC, anon, authenticated;

REVOKE ALL ON FUNCTION public.record_content_review_decision(
    UUID, UUID, public.review_decision_kind, TEXT
) FROM PUBLIC, anon, authenticated;

GRANT EXECUTE ON FUNCTION public.submit_content_for_review(UUID, UUID)
TO authenticated;

GRANT EXECUTE ON FUNCTION public.add_content_comment(UUID, UUID, UUID, TEXT)
TO authenticated;

GRANT EXECUTE ON FUNCTION public.record_content_review_decision(
    UUID, UUID, public.review_decision_kind, TEXT
) TO authenticated;
