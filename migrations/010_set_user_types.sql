-- yoyo migration script
INSERT INTO user_types(user_type_id, user_type_name)
VALUES (1, 'admin'), (2, 'internal'), (3, 'external')