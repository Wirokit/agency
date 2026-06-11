-- yoyo migration script
CREATE TABLE user_types
(
    user_type_id SERIAL PRIMARY KEY,
    user_type_name character varying(10) NOT NULL
)
