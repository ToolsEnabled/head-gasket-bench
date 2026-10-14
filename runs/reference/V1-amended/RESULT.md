# Scripted reference: V1 (standard job), amended epoch

The zero-model scripted V1 job that the paper's Table 1 uses as its reference row: 18/18 points, 13,630 s productive, 0 s penalty, 436 actions. It was produced by the environment's scripted control on the amended runtime, the same epoch the paper's three GPT exploratory runs used, and accepted by the independent scorer as part of the 13-case amended family (independent result `c4f5fe3d7e180c21217602bca42182fd38954391026f83e53ae38e11d1b973ef`, 26 exact replay pairs).

- Runtime commit `24a57135fc5d86e70e668880d8119556a40a9611`, source manifest `10967be0011b7c7808a47a108e74b1076f5141b10a5d5a7d39fa4d4087e8179b`, configuration V1 public pin `a4e22f01d85b799e0bb92b90c56d423e792a56b5134750c6aa4d4edf9b6e232e` (sealed pin `e2b962f610544b320c40c08927da3c26743c9fb9c8a71bcd1c985a0b45b07984`).
- Result: 18/18 points, S_full 1, S_partial 1.000000, failed checkpoints: none; productive 13,630 s, penalty 0 s; 436 actions, 0 refused; mistakes 0.
- Scripted process wall 207.751 s on the environment session clock; zero model or provider calls (`report.json` tokens `not_recorded`).
- The hardened-epoch family in `../../family/V1-correct/` is the same scripted job on runtime aecadda (same 18/18, 13,630 s, 436 actions).

| File | SHA-256 | Bytes |
|---|---|---:|
| `run.json` | `380c18f0420b7130d9d00ec4748e55a7b86ba6255a46e95ab249954989e02f98` | 5,513,396 |
| `actions.jsonl` | `bf14904d2ac70eef4898f7cae8eb0483c0a324b16b3ffb737311a76f361d1d1e` | 1,593,539 |
| `report.json` | `837e52fd7b16f29121a05449f044e386f94cb19c8a802197575424291a79c708` | 628,844 |

Sealed original: `run.json` `2a6bf37bf36d01d27bc2e0a2ce2a0776bd388af84dec7b473f89804770b6dec8` (5,638,693 bytes), `actions.jsonl` `d153678ad486f030349f90f69ee3d500699a42fea042ca97ff7ecf92f9aa42ac`, `report.json` `3caac74aadee6806a941ee9178126b93adb0553b6bf274bf1ddc9217383019d4`; packet `amended-v5-24a5713` (inventory `5404dcfbe2145f697eaafe257103b22ae4902097bd5bb14ace77a9f15839ed17`).

ToolsEnabled is not affiliated with or endorsed by Anthropic, OpenAI or any other AI provider.
