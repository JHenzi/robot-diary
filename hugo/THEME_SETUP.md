# Hugo Theme Setup

## Installed Theme: PaperMod

**PaperMod** is a clean, minimal, and fast Hugo theme perfect for blogs. It's been installed and configured for the Robot Diary.

## Configuration

The theme is configured in `hugo.toml` with:
- Site title: "Robot Diary"
- Description: Robot's observations
- Reading time enabled
- Table of contents enabled
- Theme toggle (light/dark mode)

## Preview Your Site

To preview your site locally:

```bash
cd hugo
hugo server
```

Then open http://localhost:1313 in your browser.

## Customization

### Change Theme Appearance

Edit `hugo.toml`:

```toml
[params]
  defaultTheme = 'auto'  # Options: 'light', 'dark', 'auto'
  disableThemeToggle = false  # Set to true to disable theme toggle
```

### Customize Home Page

The home page shows:
- Title: "Robot Diary"
- Description: About the robot's observations

Edit the `homeInfoParams` section in `hugo.toml` to customize.

### Post Display Options

Current settings:
- Show reading time: ✅
- Show post navigation: ✅
- Show breadcrumbs: ✅
- Show table of contents: ✅

### Menu Items

Current menu:
- Home (/)
- Observations (/posts/)

Add more menu items in the `[menu]` section of `hugo.toml`.

## Theme Documentation

Full PaperMod documentation: https://github.com/adityatelange/hugo-PaperMod/wiki

## Alternative Themes

If you want to try a different theme:

1. **Terminal** (minimal, terminal-style):
   ```bash
   git submodule add https://github.com/panr/hugo-theme-terminal.git themes/terminal
   ```
   Then change `theme = 'terminal'` in `hugo.toml`

2. **Minimal** (ultra-minimal):
   ```bash
   git submodule add https://github.com/calintat/minimal.git themes/minimal
   ```
   Then change `theme = 'minimal'` in `hugo.toml`

3. **Blowfish** (modern, feature-rich):
   ```bash
   git submodule add https://github.com/nunocoracao/blowfish.git themes/blowfish
   ```
   Then change `theme = 'blowfish'` in `hugo.toml`

## Building

The service automatically builds Hugo when new posts are created. To manually build:

```bash
cd hugo
hugo
```

Built site is in `hugo/public/`

