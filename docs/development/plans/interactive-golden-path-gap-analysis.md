# Interactive Golden Path capability matrix

| Product step | Backend endpoint | Request / response | Permission | Idempotency | Frontend implementation | Test coverage |
|---|---|---|---|---|---|---|
| Project | `POST .../projects` | `ProjectCreate` / `ProjectResponse` | member+ | no | create and select | Web client + tenant API |
| Upload | `POST .../source-assets`, `POST .../uploads` | bounded metadata, octets / immutable version | member+ | yes | JSON file, SHA-256, upload | source object API |
| Parse | `POST .../extractions` | empty / extraction | member+ | yes | synchronous parse | document extraction API |
| Brief candidate | `POST .../brief-extraction-runs` | pinned extraction / run | member+ | run identity | deterministic extraction | extraction and candidate tests |
| Brief accept | `POST .../accept` | accepted candidate / immutable BriefVersion | member+ | yes | candidate from GET, never fabricated | candidate review API |
| Concepts | `POST .../concept-runs` | empty / run + three candidates | member+ | yes | deterministic generation | creative API |
| Selection | `POST .../select` | empty / selection | member+ | yes | selects returned candidate | creative API |
| Script | `POST .../scripts` | empty / ScriptVersion | member+ | yes | deterministic generation | creative API |
| Storyboard | `POST .../storyboards` | valid offline mode / version | member+ | yes | deterministic generation | visual planning API |
| Shot Plan | `POST .../shot-plans` | valid offline mode / version | member+ | yes | deterministic generation | visual planning API |
| Review | `POST .../planning-reviews` | exact planning bundle / review | member+ | yes | approved exact versions | delivery API |
| Delivery | `POST .../delivery-packages` | approved IDs / immutable package | member+ | yes | exact approved bundle | delivery API |
| Export | `POST .../exports` | format / checksum metadata | member+ | yes | server-generated ZIP | delivery API |
| Download | `GET .../delivery-exports/{id}` | none / streamed bytes | read role | no | browser download | delivery API |

The UI currently performs the sequence as one guarded user action and reports each persisted
stage. Stable per-project action keys make browser retries replay-safe. Existing scoped GETs are
sufficient for individual artifact recovery; a future richer multi-page history view may add a
read-only aggregate, but it is not required to execute the persisted workflow.
