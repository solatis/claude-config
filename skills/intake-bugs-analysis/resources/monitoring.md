# Monitoring Progress

Analysis takes 2-3 minutes for ~50 bugs. Lack of immediate output is normal.

## Check progress

```bash
ls outputs/individual/*.md | wc -l
```

Show user: "Progress: 15/49 bugs analyzed (31%)..."

## Timeline to communicate

- Start: "Analysis started - this will take ~2-3 minutes for 49 bugs"
- After 30s: "Progress: X/49 bugs analyzed..."
- After 60s: "Progress: Y/49 bugs analyzed..."
- Continue until complete

## Patience rules

- Check every 30-60 seconds (not more frequently)
- Wait 30 seconds before first check
- Let current task complete before starting another
- Run only one analysis task at a time
