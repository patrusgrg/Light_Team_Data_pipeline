# GitHub Push Instructions

## Step 1: Configure Git (if not done)
```powershell
git config --global user.name "Your Name"
git config --global user.email "your.email@example.com"
```

## Step 2: Initialize Git Repository
```powershell
cd c:\Users\patrusgurung\Light_Team_Data_pipeline\research_pipeline
git init
```

## Step 3: Add Files (excluding venv)
```powershell
git add .
git status  # Verify venv is not included
```

## Step 4: Create Initial Commit
```powershell
git commit -m "Initial commit: Research pipeline project structure"
```

## Step 5: Add Remote Repository
```powershell
# Replace YOUR_USERNAME and YOUR_REPO with actual values
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
```

## Step 6: Push to GitHub
```powershell
git branch -M main
git push -u origin main
```

## Verify .gitignore Excludes venv
The .gitignore has been updated to exclude:
- venv/
- env/
- ENV/
- __pycache__/
- *.pyc
- .pytest_cache/
- data files
- logs
- and IDE files
