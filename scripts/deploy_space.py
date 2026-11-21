"""Deploys the web version to the Hugging Face Space and creates the human-plays dataset."""
from pathlib import Path

from huggingface_hub import CommitOperationAdd, CommitOperationDelete, HfApi

ROOT = Path(__file__).parent.parent
SPACE = 'inkling616/mirror-quest'
PLAYS = 'inkling616/mqbench-human-plays'
DIRS = ['space', 'mqbench', 'web', 'levels', 'leaderboard']

api = HfApi()
api.create_repo(PLAYS, repo_type='dataset', exist_ok=True)
api.upload_file(path_or_fileobj=ROOT / 'datasets/human-plays/README.md', path_in_repo='README.md',
                repo_id=PLAYS, repo_type='dataset', commit_message='Update dataset card')

api.create_repo(SPACE, repo_type='space', space_sdk='docker', exist_ok=True)
files = {'Dockerfile': ROOT / 'space/Dockerfile', 'README.md': ROOT / 'space/README.md'}
files |= {str(p.relative_to(ROOT)): p for d in DIRS for p in sorted((ROOT / d).rglob('*'))
          if p.is_file() and '__pycache__' not in p.parts}
ops = [CommitOperationAdd(dst, src) for dst, src in files.items()]
ops += [CommitOperationDelete(f) for f in api.list_repo_files(SPACE, repo_type='space') if f not in files | {'.gitattributes': None}]
api.create_commit(SPACE, repo_type='space', operations=ops, commit_message='Deploy from GitHub')
print(f'https://huggingface.co/spaces/{SPACE}')
