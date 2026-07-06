# Connection Type Patterns

These examples are dashboard runbook and review patterns. They are not active
GitOps manifests because the captured Red Hat chapter describes a dashboard
workflow.

## Dashboard Path

```text
OpenShift AI dashboard -> Settings -> Environment setup -> Connection types
```

Use Preview from the Options menu to see the form users will see when creating
a connection.

## Demo Connection Type Design Template

```text
Name: ACME S3 Object Storage
Resource name: acme-s3-object-storage
Description: Template for project connections to ACME S3-compatible object storage.
Categories: object storage
Enabled: yes

Fields:
- Endpoint URL
- Bucket
- Region
- Access key
- Secret key

Section headings:
- Object storage endpoint
- Credentials
```

Review points:

- Do not place real credential values in the template.
- Confirm the resource name before saving because it cannot be changed after
  creation.
- Use a category label to help dashboard users filter and sort connection
  types.

## Versioning Pattern

```text
Duplicate ACME S3 Object Storage.
Name the copy ACME S3 Object Storage v2.
Update fields or defaults in the copy.
Preview the user form.
Disable the old type only after new workflows have moved to v2.
```

Review points:

- Edits do not update existing user-created connections.
- Duplicating preserves a visible version trail for users and operators.

## Pre-Installed Type Pattern

```text
1. Find the pre-installed type.
2. Preview the form.
3. Duplicate the type.
4. Customize the duplicate.
5. Disable the pre-installed type if users should not select it.
```

Review points:

- Pre-installed connection types cannot be edited.
- Pre-installed connection types cannot be deleted.
- Disable pre-installed types when they should not be visible for new
  connections.

## Enablement Acceptance Matrix

| State | Expected user behavior |
|-------|------------------------|
| Enabled | Type appears when users add a connection to a project resource |
| Disabled | Type does not appear for new user connections |
| Disabled after use | Existing user-created connections remain unaffected |

## Delete Custom Type Runbook

```text
1. Confirm the type is custom.
2. Confirm active docs and workflows no longer reference it.
3. Open Settings -> Environment setup -> Connection types.
4. Preview the type if needed.
5. Choose Delete from the Options menu.
6. Type the exact connection type name.
7. Delete.
8. Confirm the type is no longer listed.
```
