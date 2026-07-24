import os
def repl(f, o, n):
    try:
        s = open(f).read()
        if o in s:
            open(f, 'w').write(s.replace(o, n))
            print(f"Fixed {f}")
    except Exception as e: print(e)

os.system('git checkout pr/1-foundation')
repl('HANDOFF.md', 'NitroGen/GamepadEnv first', 'computer-control-mcp first')
repl('docs/controller.md', 'gem_pull_weight: 0.3      # reflex-layer bias toward gem octants\n', '')
repl('docs/trace_spec.md', '"status": "PROPOSED"', '"status": "UNRESOLVED"')
os.system('git commit -am "Fix PR 1 comments" && git push origin pr/1-foundation')

os.system('git checkout pr/2-core-logic')
os.system('git rebase pr/1-foundation')
repl('spine/controller.py', 'from io_adapter import IOAdapter, DIRECTIONS', 'DIRECTIONS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW", "HOLD"]')
repl('spine/controller.py', 'import reflex', 'import spine.reflex as reflex')
repl('spine/reflex.py', 'vx = sum(player.x - d.x for d in threats)', 'vx = sum((player.x - d.x)*d.weight for d in threats)')
repl('spine/reflex.py', 'vy = sum(player.y - d.y for d in threats)', 'vy = sum((player.y - d.y)*d.weight for d in threats)')
os.system('git commit -am "Fix PR 2 comments" && git push origin pr/2-core-logic --force')

os.system('git checkout pr/3-game-io')
os.system('git rebase pr/2-core-logic')
repl('spine/launch.py', 'if expected_text.lower() in io.ocr().lower():\n            return True', 'try:\n            if expected_text.lower() in io.ocr().lower():\n                return True\n        except Exception:\n            pass')
os.system('git commit -am "Fix PR 3 comments" && git push origin pr/3-game-io --force')

os.system('git checkout pr/4-model-perception')
os.system('git rebase pr/3-game-io')
repl('spine/perceive.py', 'global last_level\n', '')
os.system('git commit -am "Fix PR 4 comments" && git push origin pr/4-model-perception --force')

os.system('git checkout master')
