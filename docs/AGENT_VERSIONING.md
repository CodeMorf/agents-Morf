# Agent versioning

## Model

- `Agent` — mutable working copy (draft)  
- `AgentVersion` — snapshot rows (`version` int, `published` bool, `snapshot` JSON, `label`)  

## Lifecycle

```
create/install → draft (published=false)
     ↓ edit (status=draft)
     ↓ publish → new immutable AgentVersion (published=true)
     ↓ restore version N → copy snapshot fields into Agent draft
```

## Rules

- Never mutate a published snapshot in place  
- PATCH on agent only updates the live draft  
- Diff endpoint: `GET /agents/{id}/versions/{a}/diff/{b}`  
- Labels like `v1.0.0` stored in snapshot metadata / label field  

## Rollback

`POST /agents/{id}/versions/{version}/restore` reloads snapshot into the draft; publish again to freeze the rolled-back config.
