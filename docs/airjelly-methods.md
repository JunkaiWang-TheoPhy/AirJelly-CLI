# AirJelly 1.0.13 Public API method reference

Generated from the shared named contracts. Input objects become the exact positional RPC args; optional tail arguments are omitted. System fields cannot be passed through restricted updates.

| Method | Group | Required gates | Named parameters |
|---|---|---|---|
| `listEvents` | events | read | `startTimeMs, endTimeMs` |
| `getTask` | tasks | read | `id` |
| `listTasks` | tasks | read | `filter?` |
| `listOpenTasks` | tasks | read | `limit?` |
| `getTaskMemories` | tasks | read | `taskId` |
| `createTask` | tasks | write, cost | `task` |
| `updateTask` | tasks | write | `id, patch` |
| `completeTask` | tasks | write | `id` |
| `reopenTask` | tasks | write | `id` |
| `archiveTask` | tasks | write | `id` |
| `unarchiveTask` | tasks | write | `id` |
| `snoozeTask` | tasks | write | `id, untilMs` |
| `createScheduledTask` | schedules | write, cost, execute | `schedule` |
| `listScheduledTasks` | schedules | read | `filter?` |
| `getScheduledTask` | schedules | read | `id` |
| `updateScheduledTask` | schedules | write, cost, execute | `id, patch` |
| `pauseScheduledTask` | schedules | write | `id` |
| `archiveScheduledTask` | schedules | write | `id` |
| `resumeScheduledTask` | schedules | write, cost, execute | `id` |
| `listScheduledTaskRuns` | schedules | read | `scheduledTaskId, limit?` |
| `listScheduledTaskUpcomingOccurrences` | schedules | read | `filter?` |
| `listScheduledTaskRunHistory` | schedules | read | `filter?` |
| `getScheduledTaskOverview` | schedules | read | `options?` |
| `runScheduledTaskNow` | schedules | write, cost, execute | `id` |
| `retryScheduledTaskRun` | schedules | write, cost, execute | `runId` |
| `searchMemory` | memories | cost | `query, filter?` |
| `listMemories` | memories | read | `filter?` |
| `getMemory` | memories | read | `id` |
| `resolveScreenshotPaths` | memories | read | `ids` |
| `listPersons` | persons | read | `(none)` |
| `getEventsForEntity` | persons | read | `entityId` |
| `getDailyAppUsage` | usage | read | `date` |
| `getAppUsageRange` | usage | read | `startDate, endDate` |
| `getTopApps` | usage | read | `startDate, endDate, limit?` |
| `getAppSessions` | usage | read | `date` |
| `getAppIcons` | usage | read | `appNames` |
| `dismissReminder` | reminders | write | `id` |
| `snoozeReminder` | reminders | write | `id, durationMinutes` |
| `getRecordingStatus` | recording | read | `(none)` |
| `getRecordingPermissions` | recording | read | `(none)` |
| `getRecordingStats` | recording | read | `(none)` |
| `startRecording` | recording | write, cost | `(none)` |
| `stopRecording` | recording | write | `(none)` |

Exact JSON schemas are available through `airjelly methods` and the MCP contract resource `airjelly://bridge/contracts`. See [English guide](airjelly.md) or [中文说明](airjelly.zh.md) for full profiles, output limits, and query semantics.
