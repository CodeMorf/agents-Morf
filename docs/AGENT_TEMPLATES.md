# Official agent templates

Ten global templates (`scope=global`). Tenants **install** a copy (`scope=tenant` draft agent + tools). Global packs are not editable by tenants.

Seed (idempotent):

```bash
python -m app.cli seed-agent-templates
```

| # | Name | Slug | Category | Memory default |
|---|------|------|----------|----------------|
| 1 | Venta AI | `sales-ai` | sales | on |
| 2 | RestaApp AI | `restaapp-ai` | hospitality | on |
| 3 | Chatbot de soporte | `support-chatbot` | support | on |
| 4 | Sucursales AI | `branches-ai` | locations | on |
| 5 | Chatbot básico | `basic-chatbot` | general | **off** |
| 6 | Programación AI | `programming-ai` | engineering | on |
| 7 | Análisis de datos AI | `data-analysis-ai` | analytics | off |
| 8 | Finanzas AI | `finance-ai` | finance | on |
| 9 | Auto Calendario AI | `auto-calendar-ai` | productivity | on |
| 10 | Departamento AI | `department-ai` | internal | on |

## Common rules

- All template tools: `execution_mode: client`
- No false confirmation without successful `tool_result`
- No VPS shell / no Agents Morf operational tables for customer business data

## Tool catalogs (summary)

### sales-ai
`sales.search_products`, `get_product`, `check_price`, `check_availability`, `create_lead`, `update_lead`, `create_quote`, `create_order_request`, `schedule_followup`, `handoff_to_human`

### restaapp-ai
`restaurant.get_menu`, `search_items`, `get_allergens`, `check_availability`, `create_reservation`, `modify_reservation`, `cancel_reservation`, `create_order`, `get_order_status`, `handoff`  
Agents Morf stores **no** menus/reservations/orders.

### support-chatbot
`support.search_articles`, `create_ticket`, `get_ticket_status`, `add_ticket_comment`, `handoff`, `collect_diagnostics`

### branches-ai
`branches.search`, `get_details`, `get_hours`, `get_services`, `check_local_availability`, `route_customer`, `request_appointment`, `handoff`

### basic-chatbot
Optional: `basic.capture_contact`, `basic.handoff`

### programming-ai
`code.list_files`, `read_file`, `search`, `write_patch`, `apply_patch`, `run_tests`, `run_lint`, `run_build`, `git_diff`, `git_status`, `prepare_commit`, `request_approval`  
No free shell; no `.env`; no auto push.

### data-analysis-ai
`data.list_sources`, `describe_source`, `execute_readonly_query`, `profile_dataset`, `aggregate`, `create_chart_spec`, `export_report`  
Readonly; charts as JSON specs.

### finance-ai
`finance.get_summary`, `get_budget`, `list_transactions`, `classify_expense`, `create_report`, `create_draft_entry`, `request_approval`, `handoff`  
No payments/transfers.

### auto-calendar-ai
`calendar.get_availability`, `find_slots`, `create_event` (+ idempotency_key), `reschedule_event`, `cancel_event`, `add_attendee`, `create_reminder`

### department-ai
`department.get_directory`, `get_policy`, `route_request`, `create_task`, `get_task_status`, `notify_responsible`, `handoff`  
Install accepts `department_profile`.

## Install flow

```
Global template → POST .../install → tenant Agent draft + Tools → test → publish
```
