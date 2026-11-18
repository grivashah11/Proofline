BEGIN;

-- ============================================================
-- PROOFLINE ROUND 3 / IMPROVEMENT 1
-- Private PDF/DOCX sources, extracted locations and Passport links.
-- All additions are additive; existing image storage and Passport
-- version lifecycle objects are intentionally left intact.
-- ============================================================

-- 1. PRIVATE SOURCE DOCUMENT BUCKET

INSERT INTO storage.buckets (
    id,
    name,
    public,
    file_size_limit,
    allowed_mime_types
)
VALUES (
    'proofline-source-documents',
    'proofline-source-documents',
    false,
    15728640,
    ARRAY[
        'application/pdf',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    ]::TEXT[]
)
ON CONFLICT (id) DO UPDATE
SET
    name = EXCLUDED.name,
    public = false,
    file_size_limit = EXCLUDED.file_size_limit,
    allowed_mime_types = EXCLUDED.allowed_mime_types;


-- 2. SOURCE DOCUMENT METADATA

CREATE TABLE public.source_documents (
    id UUID PRIMARY KEY,
    workspace_id UUID NOT NULL
        REFERENCES public.workspaces(id) ON DELETE CASCADE,

    title TEXT NOT NULL
        CHECK (char_length(btrim(title)) BETWEEN 1 AND 300),

    original_filename TEXT NOT NULL
        CHECK (char_length(original_filename) BETWEEN 1 AND 255),

    storage_path TEXT NOT NULL UNIQUE,

    mime_type TEXT NOT NULL
        CHECK (
            mime_type IN (
                'application/pdf',
                'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
            )
        ),

    document_format TEXT NOT NULL
        CHECK (document_format IN ('PDF', 'DOCX')),

    file_size_bytes INTEGER NOT NULL
        CHECK (file_size_bytes BETWEEN 1 AND 15728640),

    sha256_hash TEXT NOT NULL
        CHECK (sha256_hash ~ '^[0-9a-f]{64}$'),

    page_count INTEGER
        CHECK (page_count IS NULL OR page_count BETWEEN 1 AND 250),

    segment_count INTEGER NOT NULL
        CHECK (segment_count BETWEEN 1 AND 2500),

    extraction_warnings JSONB NOT NULL DEFAULT '[]'::JSONB
        CHECK (jsonb_typeof(extraction_warnings) = 'array'),

    uploaded_by UUID NOT NULL
        REFERENCES auth.users(id) ON DELETE RESTRICT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (workspace_id, id),
    UNIQUE (workspace_id, sha256_hash),

    CHECK (
        storage_path = (
            workspace_id::TEXT || '/source-documents/' || id::TEXT || '/' ||
            id::TEXT || CASE
                WHEN document_format = 'PDF' THEN '.pdf'
                ELSE '.docx'
            END
        )
    ),
    CHECK (
        (document_format = 'PDF' AND mime_type = 'application/pdf' AND page_count IS NOT NULL)
        OR
        (
            document_format = 'DOCX'
            AND mime_type = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
            AND page_count IS NULL
        )
    )
);

CREATE INDEX source_documents_workspace_created_idx
    ON public.source_documents(workspace_id, created_at DESC);


-- 3. IMMUTABLE EXTRACTED SOURCE SEGMENTS

CREATE TABLE public.source_document_segments (
    id UUID PRIMARY KEY,
    workspace_id UUID NOT NULL,
    source_document_id UUID NOT NULL,

    segment_index INTEGER NOT NULL
        CHECK (segment_index BETWEEN 1 AND 2500),

    location_type TEXT NOT NULL
        CHECK (location_type IN ('page', 'section', 'table_row')),

    location_label TEXT NOT NULL
        CHECK (char_length(btrim(location_label)) BETWEEN 1 AND 500),

    page_number INTEGER
        CHECK (page_number IS NULL OR page_number BETWEEN 1 AND 250),

    section_path TEXT
        CHECK (section_path IS NULL OR char_length(section_path) <= 1000),

    paragraph_number INTEGER
        CHECK (paragraph_number IS NULL OR paragraph_number >= 1),

    text_content TEXT NOT NULL
        CHECK (char_length(btrim(text_content)) BETWEEN 1 AND 20000),

    sha256_hash TEXT NOT NULL
        CHECK (sha256_hash ~ '^[0-9a-f]{64}$'),

    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT source_segments_document_fk
        FOREIGN KEY (source_document_id, workspace_id)
        REFERENCES public.source_documents(id, workspace_id)
        ON DELETE CASCADE,

    UNIQUE (source_document_id, segment_index),
    UNIQUE (id, source_document_id, workspace_id),

    CHECK (
        (location_type = 'page' AND page_number IS NOT NULL)
        OR
        (location_type IN ('section', 'table_row') AND page_number IS NULL)
    )
);

CREATE INDEX source_document_segments_document_idx
    ON public.source_document_segments(
        workspace_id,
        source_document_id,
        segment_index
    );


-- 4. LINK SOURCE EXCERPTS TO EXACT PASSPORT VERSIONS

CREATE TABLE public.claim_passport_version_sources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    workspace_id UUID NOT NULL,
    claim_passport_id UUID NOT NULL,
    passport_version_id UUID NOT NULL,
    source_document_id UUID NOT NULL,
    source_document_segment_id UUID NOT NULL,

    excerpt TEXT NOT NULL
        CHECK (char_length(btrim(excerpt)) BETWEEN 1 AND 10000),

    -- Snapshots keep historical review interpretation stable even if
    -- the source document's display metadata is ever extended later.
    location_label_snapshot TEXT NOT NULL
        CHECK (char_length(btrim(location_label_snapshot)) BETWEEN 1 AND 500),

    source_document_title_snapshot TEXT NOT NULL
        CHECK (char_length(btrim(source_document_title_snapshot)) BETWEEN 1 AND 300),

    source_document_sha256_snapshot TEXT NOT NULL
        CHECK (source_document_sha256_snapshot ~ '^[0-9a-f]{64}$'),

    created_by UUID NOT NULL
        REFERENCES auth.users(id) ON DELETE RESTRICT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT passport_source_version_fk
        FOREIGN KEY (passport_version_id, claim_passport_id, workspace_id)
        REFERENCES public.claim_passport_versions(
            id,
            claim_passport_id,
            workspace_id
        )
        ON DELETE CASCADE,

    CONSTRAINT passport_source_document_fk
        FOREIGN KEY (source_document_id, workspace_id)
        REFERENCES public.source_documents(id, workspace_id)
        ON DELETE RESTRICT,

    CONSTRAINT passport_source_segment_fk
        FOREIGN KEY (
            source_document_segment_id,
            source_document_id,
            workspace_id
        )
        REFERENCES public.source_document_segments(
            id,
            source_document_id,
            workspace_id
        )
        ON DELETE RESTRICT,

    UNIQUE (passport_version_id, source_document_segment_id, excerpt)
);

CREATE INDEX passport_version_sources_lookup_idx
    ON public.claim_passport_version_sources(
        workspace_id,
        claim_passport_id,
        passport_version_id
    );


-- 5. ROW LEVEL SECURITY

ALTER TABLE public.source_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.source_document_segments ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.claim_passport_version_sources ENABLE ROW LEVEL SECURITY;

CREATE POLICY source_documents_select_member
ON public.source_documents
FOR SELECT
TO authenticated
USING ((SELECT public.is_workspace_member(workspace_id)));

CREATE POLICY source_document_segments_select_member
ON public.source_document_segments
FOR SELECT
TO authenticated
USING ((SELECT public.is_workspace_member(workspace_id)));

CREATE POLICY passport_version_sources_select_member
ON public.claim_passport_version_sources
FOR SELECT
TO authenticated
USING ((SELECT public.is_workspace_member(workspace_id)));

REVOKE ALL ON TABLE
    public.source_documents,
    public.source_document_segments,
    public.claim_passport_version_sources
FROM anon, authenticated;

GRANT SELECT ON TABLE
    public.source_documents,
    public.source_document_segments,
    public.claim_passport_version_sources
TO authenticated;


-- 6. STORAGE ACCESS POLICIES
-- The path format is workspace-id/source-documents/document-id/file.ext.
-- Members may read; only Brand Owners may upload or rollback-delete.

CREATE POLICY proofline_source_documents_select_member
ON storage.objects
FOR SELECT
TO authenticated
USING (
    bucket_id = 'proofline-source-documents'
    AND (storage.foldername(name))[2] = 'source-documents'
    AND CASE
        WHEN (storage.foldername(name))[1]
            ~* '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
        THEN (SELECT public.is_workspace_member(
            ((storage.foldername(name))[1])::UUID
        ))
        ELSE false
    END
);

CREATE POLICY proofline_source_documents_insert_owner
ON storage.objects
FOR INSERT
TO authenticated
WITH CHECK (
    bucket_id = 'proofline-source-documents'
    AND (storage.foldername(name))[2] = 'source-documents'
    AND CASE
        WHEN (storage.foldername(name))[1]
            ~* '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
        THEN (SELECT public.has_workspace_role(
            ((storage.foldername(name))[1])::UUID,
            ARRAY['brand_owner']
        ))
        ELSE false
    END
);

CREATE POLICY proofline_source_documents_delete_owner_rollback
ON storage.objects
FOR DELETE
TO authenticated
USING (
    bucket_id = 'proofline-source-documents'
    AND (storage.foldername(name))[2] = 'source-documents'
    AND NOT EXISTS (
        SELECT 1
        FROM public.source_documents AS registered_document
        WHERE registered_document.storage_path = name
    )
    AND CASE
        WHEN (storage.foldername(name))[1]
            ~* '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
        THEN (SELECT public.has_workspace_role(
            ((storage.foldername(name))[1])::UUID,
            ARRAY['brand_owner']
        ))
        ELSE false
    END
);


-- 7. ATOMIC SOURCE DOCUMENT REGISTRATION
-- Storage upload happens first. This function atomically inserts the
-- document metadata and all extracted segments; API rollback removes
-- the just-uploaded object if this function fails.

CREATE OR REPLACE FUNCTION public.register_source_document(
    p_document JSONB,
    p_segments JSONB
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $function$
DECLARE
    v_user_id UUID;
    v_workspace_id UUID;
    v_document_id UUID;
    v_document public.source_documents%ROWTYPE;
    v_segment JSONB;
    v_expected_index INTEGER := 1;
    v_format TEXT;
    v_mime_type TEXT;
    v_extension TEXT;
    v_storage_path TEXT;
BEGIN
    v_user_id := (SELECT auth.uid());

    IF v_user_id IS NULL THEN
        RAISE EXCEPTION 'Authentication required.'
            USING ERRCODE = '42501';
    END IF;

    IF p_document IS NULL
       OR jsonb_typeof(p_document) <> 'object'
       OR p_segments IS NULL
       OR jsonb_typeof(p_segments) <> 'array'
       OR jsonb_array_length(p_segments) < 1
       OR jsonb_array_length(p_segments) > 2500
    THEN
        RAISE EXCEPTION 'Invalid source document metadata or extracted segments.'
            USING ERRCODE = '22023';
    END IF;

    v_workspace_id := (p_document->>'workspace_id')::UUID;
    v_document_id := (p_document->>'id')::UUID;
    v_format := p_document->>'document_format';
    v_mime_type := p_document->>'mime_type';
    v_extension := CASE WHEN v_format = 'PDF' THEN '.pdf' ELSE '.docx' END;
    v_storage_path := p_document->>'storage_path';

    IF NOT public.has_workspace_role(
        v_workspace_id,
        ARRAY['brand_owner']
    ) THEN
        RAISE EXCEPTION 'Brand Owner permission required.'
            USING ERRCODE = '42501';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM storage.objects AS stored_object
        WHERE stored_object.bucket_id = 'proofline-source-documents'
          AND stored_object.name = v_storage_path
    ) THEN
        RAISE EXCEPTION 'Uploaded source document object was not found in private storage.'
            USING ERRCODE = 'P0002';
    END IF;

    IF v_format NOT IN ('PDF', 'DOCX')
       OR (v_format = 'PDF' AND v_mime_type <> 'application/pdf')
       OR (
           v_format = 'DOCX'
           AND v_mime_type <> 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
       )
       OR v_storage_path <> (
           v_workspace_id::TEXT || '/source-documents/' || v_document_id::TEXT || '/' ||
           v_document_id::TEXT || v_extension
       )
       OR (p_document->>'sha256_hash') !~ '^[0-9a-f]{64}$'
       OR (p_document->>'file_size_bytes')::INTEGER NOT BETWEEN 1 AND 15728640
       OR (p_document->>'segment_count')::INTEGER <> jsonb_array_length(p_segments)
       OR (
           v_format = 'PDF'
           AND (p_document->>'page_count')::INTEGER NOT BETWEEN 1 AND 250
       )
       OR (v_format = 'DOCX' AND p_document->'page_count' <> 'null'::JSONB)
    THEN
        RAISE EXCEPTION 'Source document metadata failed validation.'
            USING ERRCODE = '22023';
    END IF;

    INSERT INTO public.source_documents (
        id,
        workspace_id,
        title,
        original_filename,
        storage_path,
        mime_type,
        document_format,
        file_size_bytes,
        sha256_hash,
        page_count,
        segment_count,
        extraction_warnings,
        uploaded_by
    )
    VALUES (
        v_document_id,
        v_workspace_id,
        NULLIF(btrim(p_document->>'title'), ''),
        p_document->>'original_filename',
        v_storage_path,
        v_mime_type,
        v_format,
        (p_document->>'file_size_bytes')::INTEGER,
        p_document->>'sha256_hash',
        NULLIF(p_document->>'page_count', '')::INTEGER,
        (p_document->>'segment_count')::INTEGER,
        COALESCE(p_document->'extraction_warnings', '[]'::JSONB),
        v_user_id
    )
    RETURNING * INTO v_document;

    FOR v_segment IN SELECT value FROM jsonb_array_elements(p_segments)
    LOOP
        IF jsonb_typeof(v_segment) <> 'object'
           OR (v_segment->>'segment_index')::INTEGER <> v_expected_index
           OR v_segment->>'location_type' NOT IN ('page', 'section', 'table_row')
           OR char_length(btrim(v_segment->>'text_content')) NOT BETWEEN 1 AND 20000
           OR (v_segment->>'sha256_hash') !~ '^[0-9a-f]{64}$'
           OR char_length(btrim(v_segment->>'location_label')) NOT BETWEEN 1 AND 500
        THEN
            RAISE EXCEPTION 'An extracted source segment failed validation.'
                USING ERRCODE = '22023';
        END IF;

        IF v_format = 'PDF'
           AND (
               v_segment->>'location_type' <> 'page'
               OR (v_segment->>'page_number')::INTEGER NOT BETWEEN 1 AND (p_document->>'page_count')::INTEGER
           )
        THEN
            RAISE EXCEPTION 'Invalid PDF page reference in extracted segment.'
                USING ERRCODE = '22023';
        END IF;

        IF v_format = 'DOCX'
           AND (
               v_segment->>'location_type' = 'page'
               OR v_segment->'page_number' <> 'null'::JSONB
           )
        THEN
            RAISE EXCEPTION 'DOCX source references must use sections or table rows.'
                USING ERRCODE = '22023';
        END IF;

        INSERT INTO public.source_document_segments (
            id,
            workspace_id,
            source_document_id,
            segment_index,
            location_type,
            location_label,
            page_number,
            section_path,
            paragraph_number,
            text_content,
            sha256_hash
        )
        VALUES (
            (v_segment->>'id')::UUID,
            v_workspace_id,
            v_document_id,
            v_expected_index,
            v_segment->>'location_type',
            v_segment->>'location_label',
            NULLIF(v_segment->>'page_number', '')::INTEGER,
            NULLIF(v_segment->>'section_path', ''),
            NULLIF(v_segment->>'paragraph_number', '')::INTEGER,
            v_segment->>'text_content',
            v_segment->>'sha256_hash'
        );

        v_expected_index := v_expected_index + 1;
    END LOOP;

    RETURN to_jsonb(v_document);
END;
$function$;

REVOKE ALL ON FUNCTION public.register_source_document(JSONB, JSONB)
FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.register_source_document(JSONB, JSONB)
TO authenticated;


-- 8. ATOMIC DOCUMENT-BACKED PASSPORT VERSION CREATION
-- A source excerpt is checked against the immutable extracted segment.
-- The new Passport version and its provenance row are inserted together.

CREATE OR REPLACE FUNCTION public.create_claim_passport_version_from_source(
    p_claim_passport_id UUID,
    p_source_document_id UUID,
    p_source_segment_id UUID,
    p_source_excerpt TEXT,
    p_version_data JSONB
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $function$
DECLARE
    v_user_id UUID;
    v_passport public.claim_passports%ROWTYPE;
    v_document public.source_documents%ROWTYPE;
    v_segment public.source_document_segments%ROWTYPE;
    v_version public.claim_passport_versions%ROWTYPE;
    v_source public.claim_passport_version_sources%ROWTYPE;
    v_next_version INTEGER;
    v_excerpt TEXT;
BEGIN
    v_user_id := (SELECT auth.uid());

    IF v_user_id IS NULL THEN
        RAISE EXCEPTION 'Authentication required.'
            USING ERRCODE = '42501';
    END IF;

    IF p_version_data IS NULL
       OR jsonb_typeof(p_version_data) <> 'object'
       OR p_source_excerpt IS NULL
       OR char_length(btrim(p_source_excerpt)) NOT BETWEEN 1 AND 10000
       OR NULLIF(btrim(p_version_data->>'approved_wording'), '') IS NULL
       OR NULLIF(btrim(p_version_data->>'subject'), '') IS NULL
       OR NULLIF(btrim(p_version_data->>'attribute'), '') IS NULL
    THEN
        RAISE EXCEPTION 'Invalid Passport version or source excerpt.'
            USING ERRCODE = '22023';
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
        RAISE EXCEPTION 'Cannot create a version for a retired Passport.'
            USING ERRCODE = 'P0001';
    END IF;

    SELECT *
    INTO v_document
    FROM public.source_documents
    WHERE id = p_source_document_id
      AND workspace_id = v_passport.workspace_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Source document not found in this workspace.'
            USING ERRCODE = 'P0002';
    END IF;

    SELECT *
    INTO v_segment
    FROM public.source_document_segments
    WHERE id = p_source_segment_id
      AND source_document_id = p_source_document_id
      AND workspace_id = v_passport.workspace_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Source segment not found in this document.'
            USING ERRCODE = 'P0002';
    END IF;

    v_excerpt := btrim(p_source_excerpt);
    IF position(v_excerpt IN v_segment.text_content) = 0 THEN
        RAISE EXCEPTION 'The selected excerpt is not present in the chosen source segment.'
            USING ERRCODE = '22023';
    END IF;

    IF NULLIF(p_version_data->>'numeric_value', '') IS NOT NULL
       AND NULLIF(p_version_data->>'unit', '') IS NULL
    THEN
        RAISE EXCEPTION 'A unit is required when a numeric value is provided.'
            USING ERRCODE = '22023';
    END IF;

    SELECT COALESCE(MAX(version_number), 0) + 1
    INTO v_next_version
    FROM public.claim_passport_versions
    WHERE claim_passport_id = p_claim_passport_id
      AND workspace_id = v_passport.workspace_id;

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
        valid_from,
        valid_until,
        evidence_source_title,
        evidence_source_url,
        evidence_reference,
        evidence_excerpt,
        evidence_source_version,
        review_by,
        owner_id,
        created_by
    )
    VALUES (
        v_passport.workspace_id,
        p_claim_passport_id,
        v_next_version,
        btrim(p_version_data->>'approved_wording'),
        btrim(p_version_data->>'subject'),
        btrim(p_version_data->>'attribute'),
        NULLIF(btrim(p_version_data->>'permitted_value'), ''),
        NULLIF(p_version_data->>'numeric_value', '')::NUMERIC(20, 6),
        NULLIF(btrim(p_version_data->>'unit'), ''),
        NULLIF(btrim(p_version_data->>'qualifier'), ''),
        NULLIF(btrim(p_version_data->>'required_conditions'), ''),
        NULLIF(btrim(p_version_data->>'product_scope'), ''),
        NULLIF(btrim(p_version_data->>'channel_scope'), ''),
        NULLIF(btrim(p_version_data->>'market_scope'), ''),
        NULLIF(p_version_data->>'valid_from', '')::DATE,
        NULLIF(p_version_data->>'valid_until', '')::DATE,
        v_document.title,
        NULL,
        v_segment.location_label,
        v_excerpt,
        'sha256:' || v_document.sha256_hash,
        NULLIF(p_version_data->>'review_by', '')::DATE,
        v_user_id,
        v_user_id
    )
    RETURNING * INTO v_version;

    INSERT INTO public.claim_passport_version_sources (
        workspace_id,
        claim_passport_id,
        passport_version_id,
        source_document_id,
        source_document_segment_id,
        excerpt,
        location_label_snapshot,
        source_document_title_snapshot,
        source_document_sha256_snapshot,
        created_by
    )
    VALUES (
        v_passport.workspace_id,
        p_claim_passport_id,
        v_version.id,
        v_document.id,
        v_segment.id,
        v_excerpt,
        v_segment.location_label,
        v_document.title,
        v_document.sha256_hash,
        v_user_id
    )
    RETURNING * INTO v_source;

    RETURN jsonb_build_object(
        'version', to_jsonb(v_version),
        'source', to_jsonb(v_source)
    );
END;
$function$;

REVOKE ALL ON FUNCTION public.create_claim_passport_version_from_source(
    UUID, UUID, UUID, TEXT, JSONB
) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.create_claim_passport_version_from_source(
    UUID, UUID, UUID, TEXT, JSONB
) TO authenticated;

COMMIT;
