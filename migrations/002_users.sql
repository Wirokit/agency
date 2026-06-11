-- yoyo migration script
CREATE TABLE users
(
    id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    username character varying(255),
    is_disabled boolean NOT NULL DEFAULT false,
    password_hash text,
    require_pw_update boolean DEFAULT true,
    full_name character varying(100) NOT NULL,
    title character varying(100) DEFAULT ''::character varying,
    office character varying(30) DEFAULT ''::character varying,
    cv_data json DEFAULT '{}'::json,
    user_type_id smallint NOT NULL,
    phone_num character varying(20) DEFAULT ''::character varying,
    email character varying(100) DEFAULT ''::character varying,
    created_at timestamp with time zone NOT NULL DEFAULT now(),
    pin_code character varying(6) DEFAULT ''::character varying,
    CONSTRAINT "unique-username" UNIQUE (username),
    CONSTRAINT fkey_user_type FOREIGN KEY (user_type_id)
        REFERENCES public.user_types (user_type_id) MATCH SIMPLE
        ON UPDATE NO ACTION
        ON DELETE NO ACTION
        NOT VALID
)
