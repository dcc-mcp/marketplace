# Built-in DCC skill migration

Base skills shipped with an adapter are already discovered when that adapter
starts. They are not marketplace packages.

If an older marketplace install exists, remove only that duplicate copy, then
reload the affected DCC:

```bash
dcc-mcp-cli marketplace uninstall dcc-mcp-maya-skills --dcc maya
dcc-mcp-cli marketplace uninstall dcc-mcp-blender-skills --dcc blender
dcc-mcp-cli marketplace uninstall dcc-mcp-houdini-skills --dcc houdini
dcc-mcp-cli reload-skills --dcc-type <dcc>
```

Uninstalling these old marketplace packages does not remove adapter-bundled
skills. Install the adapter release itself to update base skills; use the
marketplace for optional extensions, asset providers, and studio tools.
