ALTER TABLE public.workspace_members
ADD COLUMN IF NOT EXISTS display_name TEXT;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'workspace_members_display_name_length_check'
      AND conrelid = 'public.workspace_members'::regclass
  ) THEN
    ALTER TABLE public.workspace_members
      ADD CONSTRAINT workspace_members_display_name_length_check
      CHECK (
        display_name IS NULL
        OR char_length(btrim(display_name)) BETWEEN 2 AND 80
      );
  END IF;
END $$;

COMMENT ON COLUMN public.workspace_members.display_name IS
  'Human-readable name shown in workspace member lists and review activity.';
