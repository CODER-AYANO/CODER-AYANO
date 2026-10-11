# Kitsune Contribution Arcade 🦊

A dark Japanese kitsune-inspired contribution calendar for the `CODER-AYANO` GitHub profile. It reads real GitHub contribution data and generates a gold/crimson SVG.

## Install
1. Put these files in your profile repository (usually named exactly `CODER-AYANO`).
2. In **Settings → Secrets and variables → Actions**, create a repository secret named `GH_PROFILE_TOKEN` containing a GitHub token that can query your profile through GraphQL.
3. Open **Actions → Kitsune Contribution Arcade → Run workflow**.
4. Add this to your profile README:

   `![Kitsune Contribution Arcade](./assets/kitsune-arcade.svg)`

If your GitHub username differs, change `PROFILE_LOGIN` in `.github/workflows/kitsune-arcade.yml`.

The SVG uses SVG motion, which some GitHub rendering contexts may display as a static image. The contribution heatmap still appears. This is a visual animation, not a game that changes contribution counts.
