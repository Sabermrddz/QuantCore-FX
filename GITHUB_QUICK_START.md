# GitHub Setup — QUICK START (5 Minutes)

## **🚀 TL;DR — Copy & Paste**

### **1. Create GitHub Repository**
- Go to [github.com](https://github.com)
- Click **"+" → New repository**
- Name: `apex_layer1`
- Select **"Add .gitignore: Python"**
- Click **"Create repository"**
- **Copy the HTTPS URL** (looks like: `https://github.com/YOUR_USERNAME/apex_layer1.git`)

### **2. Open PowerShell**
```powershell
cd "c:\Users\sober\Desktop\QuantCore FX\apex_layer1"

# First time setup
git config --global user.name "Your Name"
git config --global user.email "your.email@gmail.com"

# Initialize Git
git init

# Add all files
git add .

# Create first commit
git commit -m "Initial commit: APEX Layer 1 — Currency Strength Engine"

# Add remote (replace with YOUR URL from GitHub)
git remote add origin https://github.com/YOUR_USERNAME/apex_layer1.git

# Rename branch to main
git branch -M main

# Push to GitHub
git push -u origin main
```

### **3. Authenticate**
When GitHub asks for password:
- Use your **Personal Access Token** (not your password)

**To create a token:**
1. GitHub → Settings → Developer settings → Personal access tokens
2. Click "Generate new token"
3. Name: `apex_layer1`
4. Scope: ✅ `repo`
5. Copy token
6. Paste when prompted

---

## **✅ Verify**
- Refresh GitHub in browser
- See your files? ✅ Success!

---

## **📝 Future Updates** (Easy)
```powershell
# After making changes:
git add .
git commit -m "Description of what changed"
git push origin main
```

---

## **❓ Need Help?**
See [GITHUB_SETUP_GUIDE.md](GITHUB_SETUP_GUIDE.md) for detailed instructions & troubleshooting.
