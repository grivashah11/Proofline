BEGIN;

ALTER TABLE public.brand_rules
    ADD COLUMN check_type TEXT NOT NULL DEFAULT 'manual_review',
    ADD COLUMN check_value TEXT;

ALTER TABLE public.brand_rules
    ADD CONSTRAINT brand_rules_check_type_valid
    CHECK (
        check_type IN (
            'manual_review',
            'contains_phrase',
            'does_not_contain_phrase',
            'min_characters',
            'max_characters'
        )
    );

ALTER TABLE public.brand_rules
    ADD CONSTRAINT brand_rules_check_value_valid
    CHECK (
        CASE
            WHEN check_type = 'manual_review'
            THEN check_value IS NULL

            WHEN check_type IN (
                'contains_phrase',
                'does_not_contain_phrase'
            )
            THEN
                check_value IS NOT NULL
                AND char_length(btrim(check_value)) BETWEEN 1 AND 500

            WHEN check_type = 'min_characters'
            THEN
                CASE
                    WHEN check_value ~ '^(0|[1-9][0-9]{0,4})$'
                    THEN check_value::integer <= 50000
                    ELSE false
                END

            WHEN check_type = 'max_characters'
            THEN
                CASE
                    WHEN check_value ~ '^[1-9][0-9]{0,4}$'
                    THEN check_value::integer <= 50000
                    ELSE false
                END

            ELSE false
        END
    );

ALTER TABLE public.brand_rules
    ADD CONSTRAINT brand_rules_automatic_check_kind_valid
    CHECK (
        rule_kind IN ('messaging', 'channel_guidance')
        OR check_type = 'manual_review'
    );

GRANT UPDATE (
    check_type,
    check_value
)
ON public.brand_rules
TO authenticated;

COMMIT;