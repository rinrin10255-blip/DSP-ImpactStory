# DSP-ImpactStory
Lin brunch dsp program
# Data-Systems-Project---UvA-Impact-Story-Generation
Repository for the development of a Python-based (web)application designed to assist in the generation of impact stories through the (partial) automation of data collection, processing, and story development.

## Version Control and Collaborative Working

This project follows a structured **Git-based version control and collaborative workflow** to ensure efficient development and clear version management.

---

### **1. Git Branching Strategy**
Team should follow a **Trunk-Based Development** approach with feature branches. The primary branches in the repository are:

#### **Main Branch (`main`)**
- The production-ready, stable branch.
- Only code that has passed **all tests and reviews** should be merged.
- Protected against direct pushes; requires **PR review & CI/CD validation**.

#### **Feature Branches (`feature/*`)**
- Used for new features, enhancements, or experimental code.
- Must be based on `main` and merged back via **Pull Requests (PRs)**.
- Example: `feature/dasbboard`, `feature/genAI-prompter`

### **2. Git Commit and Pull Request Workflow**
#### **Step-by-Step Workflow for Everyone:**

1. **Update `main` locally**
   ```sh
   git checkout main
   ```
   
   ```sh
   git pull origin main
   ```

2. **Create a new feature branch**
   ```sh
   git checkout -b feature/my-new-feature
   ```
   
   or if feature branch already exists
   ```sh
   git checkout feature/my-new-feature
   ```

3. **Develop and commit changes**
   ```sh
   git add .
   ```

   ```sh
   git commit -m "commit message"
   ```

4. **Push the branch to the remote repository**
   ```sh
   git push origin feature/my-new-feature
   ```
   **DO NOT push directly to the `main` branch.**

6. **Create a Pull Request (PR) in GitHub**
   - PR must be **reviewed and approved** before merging into `main`.
