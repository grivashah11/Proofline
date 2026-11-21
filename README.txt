Proofline route navigation fix

This patch only replaces frontend/src/App.tsx.
It fixes the account-change redirect so it runs once per signed-in account ID.
It does not change routes, authentication, roles, backend APIs, database data,
or environment files.
