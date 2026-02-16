from story_manager import StoryManager

sm = StoryManager()
print("Providers loaded:")
for p in sm.source_manager.providers:
    print(f"- {getattr(p, 'key', 'Unknown')}")

has_qq = any(getattr(p, 'key', '') == 'questionablequesting' for p in sm.source_manager.providers)
has_qq_all = any(getattr(p, 'key', '') == 'questionablequesting_all' for p in sm.source_manager.providers)

if has_qq and has_qq_all:
    print("PASS: Both QQ providers loaded.")
else:
    print("FAIL: Missing a QQ provider.")
