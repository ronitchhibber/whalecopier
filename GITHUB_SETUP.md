# GitHub Setup Guide

## Quick Setup - Create GitHub Repo and Push

### Step 1: Create GitHub Repository

1. Go to https://github.com/new
2. **Repository name**: `polymarket-whale-copier` (or your preferred name)
3. **Description**: Production-grade institutional whale copy-trading system for Polymarket
4. **Visibility**:
   - ⚠️ **PRIVATE** (Recommended - contains trading strategy)
   - OR Public (if you want to share)
5. **DO NOT** initialize with README, .gitignore, or license (we already have these)
6. Click "Create repository"

### Step 2: Configure Git User (One-time setup)

```bash
git config --global user.name "Your Name"
git config --global user.email "your.email@example.com"
```

### Step 3: Push to GitHub

After creating the repo on GitHub, you'll see instructions. Use these commands:

```bash
# Navigate to your project
cd /Users/ronitchhibber/Desktop/Polymarket_Whale_Copy

# Add GitHub remote (replace YOUR_USERNAME with your GitHub username)
git remote add origin https://github.com/YOUR_USERNAME/polymarket-whale-copier.git

# Verify remote was added
git remote -v

# Push to GitHub
git push -u origin main
```

### Step 4: Enter Credentials

When prompted:
- **Username**: Your GitHub username
- **Password**: Your GitHub Personal Access Token (NOT your password!)

#### Creating a Personal Access Token (if needed):
1. Go to https://github.com/settings/tokens
2. Click "Generate new token (classic)"
3. Give it a descriptive name: "Polymarket Copy-Trader"
4. Select scopes:
   - ✅ `repo` (full control of private repositories)
   - ✅ `workflow` (for GitHub Actions)
5. Click "Generate token"
6. **COPY THE TOKEN** - you won't see it again!
7. Use this token as your password when pushing

### Alternative: Using SSH (Recommended for frequent pushes)

```bash
# Generate SSH key (if you don't have one)
ssh-keygen -t ed25519 -C "your.email@example.com"

# Start the ssh-agent
eval "$(ssh-agent -s)"

# Add your SSH key
ssh-add ~/.ssh/id_ed25519

# Copy the public key
cat ~/.ssh/id_ed25519.pub
# Copy the output

# Add to GitHub:
# 1. Go to https://github.com/settings/keys
# 2. Click "New SSH key"
# 3. Paste your key
# 4. Click "Add SSH key"

# Change remote to SSH
git remote set-url origin git@github.com:YOUR_USERNAME/polymarket-whale-copier.git

# Push
git push -u origin main
```

## Verify Setup

After pushing, visit your GitHub repository:
```
https://github.com/YOUR_USERNAME/polymarket-whale-copier
```

You should see:
- ✅ All project files
- ✅ README.md rendered on the homepage
- ✅ GitHub Actions CI/CD workflow in the "Actions" tab

## Setting Up GitHub Secrets (for CI/CD)

For the CI/CD pipeline to work, add these secrets to your GitHub repo:

1. Go to your repo on GitHub
2. Click "Settings" → "Secrets and variables" → "Actions"
3. Click "New repository secret"

### Required Secrets:

| Secret Name | Description | How to get |
|-------------|-------------|------------|
| `DOCKERHUB_USERNAME` | Your Docker Hub username | Sign up at https://hub.docker.com |
| `DOCKERHUB_TOKEN` | Docker Hub access token | https://hub.docker.com/settings/security → "New Access Token" |
| `SLACK_WEBHOOK_URL` | (Optional) Slack webhook for notifications | https://api.slack.com/messaging/webhooks |

## Next Steps

After pushing to GitHub:

1. **Enable GitHub Actions**:
   - Go to "Actions" tab
   - Click "I understand my workflows, go ahead and enable them"

2. **Protect Main Branch**:
   - Settings → Branches → Add rule
   - Branch name pattern: `main`
   - Enable:
     - ✅ Require pull request reviews before merging
     - ✅ Require status checks to pass before merging
     - ✅ Require branches to be up to date before merging

3. **Add Collaborators** (if working with a team):
   - Settings → Collaborators → Add people

## Workflow for Future Changes

```bash
# Make changes to your code
# ...

# Stage changes
git add .

# Commit with descriptive message
git commit -m "Add whale scoring engine implementation"

# Push to GitHub
git push origin main

# Or create a feature branch:
git checkout -b feature/whale-scoring
git add .
git commit -m "Implement multi-factor whale scoring"
git push origin feature/whale-scoring
# Then create a Pull Request on GitHub
```

## Troubleshooting

### Error: "remote origin already exists"
```bash
git remote remove origin
git remote add origin https://github.com/YOUR_USERNAME/polymarket-whale-copier.git
```

### Error: "Authentication failed"
- Make sure you're using a Personal Access Token, not your GitHub password
- Token must have `repo` and `workflow` scopes

### Error: "Updates were rejected"
```bash
# If you need to force push (CAREFUL - only if you're sure)
git push -f origin main

# Or pull and merge first
git pull origin main
git push origin main
```

## Keep Both Directories in Sync

If you want to work from the original location and sync to Desktop:

```bash
# In /Users/ronitchhibber/polymarket-copy-trader
git push origin main

# Then in /Users/ronitchhibber/Desktop/Polymarket_Whale_Copy
git pull origin main
```

Or use symlinks to keep them synchronized:
```bash
rm -rf /Users/ronitchhibber/Desktop/Polymarket_Whale_Copy
ln -s /Users/ronitchhibber/polymarket-copy-trader /Users/ronitchhibber/Desktop/Polymarket_Whale_Copy
```

---

**You're all set! Your production-ready trading system is now on GitHub. 🚀**
