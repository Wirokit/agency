-- yoyo migration script
CREATE TABLE cv
(
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    date_created timestamp with time zone DEFAULT now(),
    date_updated timestamp with time zone DEFAULT now(),
    owner_id uuid NOT NULL,
    name character varying(255) COLLATE pg_catalog."default",
    title character varying(255) COLLATE pg_catalog."default",
    is_source boolean DEFAULT false,
    handler_id uuid,
    job_name character varying(255),
    CONSTRAINT fkey_handler FOREIGN KEY (handler_id)
        REFERENCES public.users (id) MATCH SIMPLE
        ON UPDATE NO ACTION
        ON DELETE NO ACTION
        NOT VALID,
    CONSTRAINT fkey_owner FOREIGN KEY (owner_id)
        REFERENCES public.users (id) MATCH SIMPLE
        ON UPDATE RESTRICT
        ON DELETE CASCADE
)
