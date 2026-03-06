# Adding a New Plugin

## Checklist

1. **Create the command file:**
   ```
   plugins/<name>/commands/<name>.md
   ```

2. **Create the plugin manifest:**
   ```
   plugins/<name>/.claude-plugin/plugin.json
   ```
   Use this template:
   ```json
   {
     "name": "your-plugin-name",
     "version": "1.0.0",
     "description": "One-line description",
     "author": {
       "name": "Yang Joon Kim",
       "url": "https://github.com/yangjun9095"
     },
     "repository": "https://github.com/yangjun9095/claude-plugins",
     "license": "MIT",
     "keywords": ["tag1", "tag2"]
   }
   ```

3. **Register in the marketplace:**
   Add an entry to `.claude-plugin/marketplace.json`:
   ```json
   {
     "name": "your-plugin-name",
     "source": "./plugins/your-plugin-name",
     "description": "One-line description",
     "version": "1.0.0"
   }
   ```

4. **Commit and push.**

## Known `plugin.json` Gotchas

- `author` **must be an object** `{"name": "...", "url": "..."}` — a plain string fails validation
- **No `commands` field** — Claude auto-discovers from the `commands/` directory
- If you add skills instead of commands, use `"skills": "./skills/<name>"`

## Testing After a Change

If you push a fix and the install still fails with the old error, the local cache is stale. Clear it:

```bash
claude plugin marketplace remove yangjun9095-plugins
claude plugin marketplace add yangjun9095/claude-plugins
claude plugin install <name>@yangjun9095-plugins
```
