BEGIN;

-- ============================================================
-- PROOFLINE STATIC IMAGE ASSETS AND CHECKS
-- ============================================================

-- A single private bucket stores both approved brand assets and
-- creator-submitted image checks. Workspace ID is always the first
-- object-path segment; the second segment identifies the object type.

INSERT INTO storage.buckets (
    id,
    name,
    public,
    file_size_limit,
    allowed_mime_types
)
VALUES (
    'proofline-workspace-images',
    'proofline-workspace-images',
    false,
    8388608,
    ARRAY['image/jpeg', 'image/png', 'image/webp']::TEXT[]
)
ON CONFLICT (id) DO UPDATE
SET
    name = EXCLUDED.name,
    public = false,
    file_size_limit = EXCLUDED.file_size_limit,
    allowed_mime_types = EXCLUDED.allowed_mime_types;


-- ============================================================
-- 1. APPROVED BRAND ASSETS
-- ============================================================

CREATE TABLE public.brand_assets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    workspace_id UUID NOT NULL
        REFERENCES public.workspaces(id) ON DELETE CASCADE,

    asset_name TEXT NOT NULL
        CHECK (char_length(btrim(asset_name)) BETWEEN 2 AND 120),

    description TEXT
        CHECK (description IS NULL OR char_length(description) <= 2000),

    original_filename TEXT NOT NULL
        CHECK (char_length(original_filename) BETWEEN 1 AND 255),

    storage_path TEXT NOT NULL UNIQUE
        CHECK (storage_path LIKE (workspace_id::TEXT || '/brand-assets/%')),

    mime_type TEXT NOT NULL
        CHECK (mime_type IN ('image/jpeg', 'image/png', 'image/webp')),

    file_size_bytes INTEGER NOT NULL
        CHECK (file_size_bytes BETWEEN 1 AND 8388608),

    sha256_hash TEXT NOT NULL
        CHECK (sha256_hash ~ '^[0-9a-f]{64}$'),

    image_format TEXT NOT NULL
        CHECK (image_format IN ('JPEG', 'PNG', 'WEBP')),

    width INTEGER NOT NULL CHECK (width BETWEEN 1 AND 8000),
    height INTEGER NOT NULL CHECK (height BETWEEN 1 AND 8000),

    dominant_colors JSONB NOT NULL DEFAULT '[]'::JSONB
        CHECK (jsonb_typeof(dominant_colors) = 'array'),

    is_active BOOLEAN NOT NULL DEFAULT true,

    created_by UUID NOT NULL
        REFERENCES auth.users(id) ON DELETE RESTRICT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (workspace_id, id),
    UNIQUE (workspace_id, sha256_hash),
    UNIQUE (workspace_id, asset_name)
);

CREATE INDEX brand_assets_workspace_active_idx
    ON public.brand_assets(workspace_id, is_active, created_at DESC);


-- ============================================================
-- 2. IMAGE CHECK RESULTS
-- ============================================================

CREATE TABLE public.image_checks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    workspace_id UUID NOT NULL
        REFERENCES public.workspaces(id) ON DELETE CASCADE,

    storage_path TEXT NOT NULL UNIQUE
        CHECK (storage_path LIKE (workspace_id::TEXT || '/image-checks/%')),

    original_filename TEXT NOT NULL
        CHECK (char_length(original_filename) BETWEEN 1 AND 255),

    mime_type TEXT NOT NULL
        CHECK (mime_type IN ('image/jpeg', 'image/png', 'image/webp')),

    file_size_bytes INTEGER NOT NULL
        CHECK (file_size_bytes BETWEEN 1 AND 8388608),

    sha256_hash TEXT NOT NULL
        CHECK (sha256_hash ~ '^[0-9a-f]{64}$'),

    image_format TEXT NOT NULL
        CHECK (image_format IN ('JPEG', 'PNG', 'WEBP')),

    width INTEGER NOT NULL CHECK (width BETWEEN 1 AND 8000),
    height INTEGER NOT NULL CHECK (height BETWEEN 1 AND 8000),

    alt_text TEXT
        CHECK (alt_text IS NULL OR char_length(alt_text) <= 1000),

    matched_asset_id UUID,

    analysis JSONB NOT NULL
        CHECK (jsonb_typeof(analysis) = 'object'),

    created_by UUID NOT NULL
        REFERENCES auth.users(id) ON DELETE RESTRICT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT image_checks_matched_asset_workspace_fk
        FOREIGN KEY (workspace_id, matched_asset_id)
        REFERENCES public.brand_assets(workspace_id, id)
);

CREATE INDEX image_checks_workspace_created_idx
    ON public.image_checks(workspace_id, created_at DESC);

CREATE INDEX image_checks_workspace_hash_idx
    ON public.image_checks(workspace_id, sha256_hash);


-- ============================================================
-- 3. UPDATED_AT TRIGGER
-- ============================================================

CREATE TRIGGER trg_brand_assets_set_updated_at
BEFORE UPDATE ON public.brand_assets
FOR EACH ROW
EXECUTE FUNCTION public.set_updated_at();


-- ============================================================
-- 4. ROW LEVEL SECURITY
-- ============================================================

ALTER TABLE public.brand_assets ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.image_checks ENABLE ROW LEVEL SECURITY;

CREATE POLICY brand_assets_select_member
ON public.brand_assets
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

CREATE POLICY brand_assets_insert_owner
ON public.brand_assets
FOR INSERT
TO authenticated
WITH CHECK (
    (SELECT public.has_workspace_role(
        workspace_id,
        ARRAY['brand_owner']
    ))
    AND created_by = (SELECT auth.uid())
);

CREATE POLICY brand_assets_update_owner
ON public.brand_assets
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

CREATE POLICY image_checks_select_member
ON public.image_checks
FOR SELECT
TO authenticated
USING (
    (SELECT public.is_workspace_member(workspace_id))
);

CREATE POLICY image_checks_insert_member
ON public.image_checks
FOR INSERT
TO authenticated
WITH CHECK (
    (SELECT public.is_workspace_member(workspace_id))
    AND created_by = (SELECT auth.uid())
);


-- ============================================================
-- 5. PRIVATE STORAGE ACCESS POLICIES
-- ============================================================

-- Guard UUID casts with CASE so malformed object paths cannot cause
-- a cast error while evaluating a Storage RLS policy.

CREATE POLICY proofline_workspace_images_select_member
ON storage.objects
FOR SELECT
TO authenticated
USING (
    bucket_id = 'proofline-workspace-images'
    AND CASE
        WHEN (storage.foldername(name))[1]
            ~* '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
        THEN (SELECT public.is_workspace_member(
            ((storage.foldername(name))[1])::UUID
        ))
        ELSE false
    END
);

CREATE POLICY proofline_workspace_images_insert_brand_assets
ON storage.objects
FOR INSERT
TO authenticated
WITH CHECK (
    bucket_id = 'proofline-workspace-images'
    AND (storage.foldername(name))[2] = 'brand-assets'
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

CREATE POLICY proofline_workspace_images_insert_image_checks
ON storage.objects
FOR INSERT
TO authenticated
WITH CHECK (
    bucket_id = 'proofline-workspace-images'
    AND (storage.foldername(name))[2] = 'image-checks'
    AND (storage.foldername(name))[3] = (SELECT auth.uid())::TEXT
    AND CASE
        WHEN (storage.foldername(name))[1]
            ~* '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
        THEN (SELECT public.is_workspace_member(
            ((storage.foldername(name))[1])::UUID
        ))
        ELSE false
    END
);

CREATE POLICY proofline_workspace_images_delete_brand_assets_rollback
ON storage.objects
FOR DELETE
TO authenticated
USING (
    bucket_id = 'proofline-workspace-images'
    AND (storage.foldername(name))[2] = 'brand-assets'
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

CREATE POLICY proofline_workspace_images_delete_image_checks_rollback
ON storage.objects
FOR DELETE
TO authenticated
USING (
    bucket_id = 'proofline-workspace-images'
    AND (storage.foldername(name))[2] = 'image-checks'
    AND (storage.foldername(name))[3] = (SELECT auth.uid())::TEXT
    AND CASE
        WHEN (storage.foldername(name))[1]
            ~* '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
        THEN (SELECT public.is_workspace_member(
            ((storage.foldername(name))[1])::UUID
        ))
        ELSE false
    END
);


-- ============================================================
-- 6. TABLE AND COLUMN PRIVILEGES
-- ============================================================

REVOKE ALL ON TABLE public.brand_assets, public.image_checks
FROM anon, authenticated;

GRANT SELECT, INSERT ON public.brand_assets TO authenticated;
GRANT UPDATE (asset_name, description, is_active)
ON public.brand_assets TO authenticated;

GRANT SELECT, INSERT ON public.image_checks TO authenticated;

COMMIT;
