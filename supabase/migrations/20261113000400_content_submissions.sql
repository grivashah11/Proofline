
CREATE TYPE public.content_type AS ENUM (
    'social_post',
    'advertisement',
    'email',
    'document',
    'other'
);

CREATE TYPE public.content_status AS ENUM (
    'draft',
    'in_review',
    'approved',
    'changes_requested',
    'rejected',
    'archived'
);

CREATE TABLE public.contents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    workspace_id UUID NOT NULL
        REFERENCES public.workspaces(id) ON DELETE CASCADE,

    title TEXT NOT NULL
        CHECK (
            char_length(btrim(title)) BETWEEN 1 AND 200
        ),

    content_type public.content_type NOT NULL,

    product_context TEXT
        CHECK (
            product_context IS NULL
            OR char_length(product_context) <= 300
        ),

    channel TEXT
        CHECK (
            channel IS NULL OR char_length(channel) <= 80
        ),

    market TEXT
        CHECK (
            market IS NULL OR char_length(market) <= 100
        ),

    status public.content_status NOT NULL DEFAULT 'draft',

    current_revision_id UUID,

    created_by UUID NOT NULL
        REFERENCES auth.users(id) ON DELETE RESTRICT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (workspace_id, id)
);

CREATE TABLE public.content_revisions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    workspace_id UUID NOT NULL,

    content_id UUID NOT NULL,

    revision_number INTEGER NOT NULL
        CHECK (revision_number >= 1),

    content_text TEXT NOT NULL
        CHECK (
            char_length(btrim(content_text)) BETWEEN 1 AND 50000
        ),

    created_by UUID NOT NULL
        REFERENCES auth.users(id) ON DELETE RESTRICT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT content_revisions_content_fk
        FOREIGN KEY (workspace_id, content_id)
        REFERENCES public.contents(workspace_id, id)
        ON DELETE CASCADE,

    UNIQUE (content_id, revision_number),

    UNIQUE (workspace_id, id)
);

ALTER TABLE public.contents
ADD CONSTRAINT contents_current_revision_fk
FOREIGN KEY (workspace_id, current_revision_id)
REFERENCES public.content_revisions(workspace_id, id)
ON DELETE RESTRICT;

CREATE INDEX contents_workspace_created_idx
ON public.contents(workspace_id, created_at DESC);

CREATE INDEX contents_workspace_status_idx
ON public.contents(workspace_id, status);

CREATE INDEX content_revisions_content_number_idx
ON public.content_revisions(content_id, revision_number DESC);

CREATE TRIGGER trg_contents_updated_at
BEFORE UPDATE ON public.contents
FOR EACH ROW
EXECUTE FUNCTION public.set_updated_at();

ALTER TABLE public.contents ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.content_revisions ENABLE ROW LEVEL SECURITY;

CREATE POLICY contents_select_member
ON public.contents
FOR SELECT
TO authenticated
USING (
    (SELECT public.is_workspace_member(workspace_id))
);

CREATE POLICY content_revisions_select_member
ON public.content_revisions
FOR SELECT
TO authenticated
USING (
    (SELECT public.is_workspace_member(workspace_id))
);

REVOKE ALL ON public.contents FROM anon, authenticated;
REVOKE ALL ON public.content_revisions FROM anon, authenticated;

GRANT SELECT ON public.contents TO authenticated;
GRANT SELECT ON public.content_revisions TO authenticated;


CREATE OR REPLACE FUNCTION public.create_content_with_revision(
    p_workspace_id UUID,
    p_title TEXT,
    p_content_type public.content_type,
    p_product_context TEXT,
    p_channel TEXT,
    p_market TEXT,
    p_content_text TEXT
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $function$
DECLARE
    v_user_id UUID;
    v_content public.contents%ROWTYPE;
    v_revision public.content_revisions%ROWTYPE;
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

    IF p_title IS NULL
       OR char_length(btrim(p_title)) NOT BETWEEN 1 AND 200
       OR p_content_text IS NULL
       OR char_length(btrim(p_content_text)) NOT BETWEEN 1 AND 50000
    THEN
        RAISE EXCEPTION 'Invalid content data.'
            USING ERRCODE = '22023';
    END IF;

    INSERT INTO public.contents (
        workspace_id,
        title,
        content_type,
        product_context,
        channel,
        market,
        created_by
    )
    VALUES (
        p_workspace_id,
        btrim(p_title),
        p_content_type,
        NULLIF(btrim(p_product_context), ''),
        NULLIF(btrim(p_channel), ''),
        NULLIF(btrim(p_market), ''),
        v_user_id
    )
    RETURNING * INTO v_content;

    INSERT INTO public.content_revisions (
        workspace_id,
        content_id,
        revision_number,
        content_text,
        created_by
    )
    VALUES (
        p_workspace_id,
        v_content.id,
        1,
        p_content_text,
        v_user_id
    )
    RETURNING * INTO v_revision;

    UPDATE public.contents
    SET current_revision_id = v_revision.id
    WHERE id = v_content.id
    RETURNING * INTO v_content;

    RETURN jsonb_build_object(
        'content', to_jsonb(v_content),
        'revision', to_jsonb(v_revision)
    );
END;
$function$;


CREATE OR REPLACE FUNCTION public.create_content_revision(
    p_workspace_id UUID,
    p_content_id UUID,
    p_content_text TEXT
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $function$
DECLARE
    v_user_id UUID;
    v_content public.contents%ROWTYPE;
    v_revision public.content_revisions%ROWTYPE;
    v_next_number INTEGER;
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

    IF p_content_text IS NULL
       OR char_length(btrim(p_content_text)) NOT BETWEEN 1 AND 50000
    THEN
        RAISE EXCEPTION 'Invalid revision content.'
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
        RAISE EXCEPTION 'Archived content cannot be revised.'
            USING ERRCODE = 'P0001';
    END IF;

    SELECT COALESCE(MAX(revision_number), 0) + 1
    INTO v_next_number
    FROM public.content_revisions
    WHERE content_id = p_content_id;

    INSERT INTO public.content_revisions (
        workspace_id,
        content_id,
        revision_number,
        content_text,
        created_by
    )
    VALUES (
        p_workspace_id,
        p_content_id,
        v_next_number,
        p_content_text,
        v_user_id
    )
    RETURNING * INTO v_revision;

    UPDATE public.contents
    SET
        current_revision_id = v_revision.id,
        status = 'draft'
    WHERE id = p_content_id
    RETURNING * INTO v_content;

    RETURN jsonb_build_object(
        'content', to_jsonb(v_content),
        'revision', to_jsonb(v_revision)
    );
END;
$function$;

REVOKE ALL ON FUNCTION public.create_content_with_revision(
    UUID, TEXT, public.content_type, TEXT, TEXT, TEXT, TEXT
) FROM PUBLIC, anon, authenticated;

REVOKE ALL ON FUNCTION public.create_content_revision(
    UUID, UUID, TEXT
) FROM PUBLIC, anon, authenticated;

GRANT EXECUTE ON FUNCTION public.create_content_with_revision(
    UUID, TEXT, public.content_type, TEXT, TEXT, TEXT, TEXT
) TO authenticated;

GRANT EXECUTE ON FUNCTION public.create_content_revision(
    UUID, UUID, TEXT
) TO authenticated;
