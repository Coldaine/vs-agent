import os

def repl(f, o, n):
    try:
        s = open(f).read()
        if o in s:
            open(f, 'w').write(s.replace(o, n))
            print(f"Fixed {f}")
    except Exception as e: print(e)

print("Starting fix_prs_2.py for PRs 5 and 6...")

os.system('git checkout pr/5-episode-harness')
os.system('git rebase pr/4-model-perception')
repl('spine/run.py', 'launch.select_option(io, 1, options)', 'launch.select_option(io, options[0] if options else "", options)')
repl('spine/run.py', 'latencies, start = [], time.monotonic()', 'latencies = []')
repl('spine/run.py', 'launch.to_stage_select(io, cfg)          # launch + menu macro\n        launch.start_run(io, cfg)', 'launch.to_stage_select(io, cfg)          # launch + menu macro\n        launch.start_run(io, cfg)\n        start = time.monotonic()')
repl('spine/verify_g0.py', 'print("[G0] Verifying Capture...")', 'print("[G0] Verifying Capture...")\n    launch.launch_game(cfg, io)')
os.system('git commit -am "Fix PR 5 comments" && git push origin pr/5-episode-harness --force')

os.system('git checkout pr/6-eval-pipeline')
os.system('git rebase pr/5-episode-harness')
repl('spine/review.py', 'median_rate = sum', 'mean_rate = sum')
repl('spine/review.py', 'run median', 'run mean')
os.system('git commit -am "Fix PR 6 comments" && git push origin pr/6-eval-pipeline --force')

os.system('git checkout master')
print("All fixes applied and pushed!")
