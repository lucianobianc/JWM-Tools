# Theme palette review

The 34 existing preset names and collections are retained. A built-in preset is
an adaptation to JWM, not a skin engine for another desktop. Existing custom
JSON styles keep their saved colors: opening the editor does not migrate or
rewrite them. Revised presets take effect only when selected and applied.

## Interface and color principles

- Give the title, panel, menu, selection, tooltip and inactive controls separate
  roles. A historical desktop is more than its title-bar accent.
- Use dark, low-luminance surfaces and limited luminous accents in Hacker;
  use light neutral menu surfaces in Modern and Chromatic, keeping the accent
  for focus and selection rather than coloring every surface identically.
- Distinguish active, inactive and minimized tasks without making inactive text
  illegible. The pager has one Text color in JWM, so its active/inactive backgrounds
  must both support that text color.
- Select text colors using linearized sRGB relative luminance and contrast,
  targeting **4.5:1** for the generated text/background pairs. Gradients are
  sampled, not judged by a simple average RGB brightness threshold. Hacker
  text accents can be lightened slightly to meet this target while keeping
  their hue. These checks do not certify the complete desktop as accessible.
- Apply Flat or Motif consistently to window frames, tray, task list and menus.
  Popup and Pager styles do not receive unsupported decoration attributes.
- Use portable Sans/Monospace aliases. The original proprietary fonts, icons,
  title-button bitmaps, wallpaper and application widget skins are not bundled.

The contrast calculation follows the [WCAG definition of relative
luminance](https://www.w3.org/TR/WCAG22/#dfn-relative-luminance) and the
[normal-text contrast criterion](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html).
Color harmony comes from each existing palette's related tones; component roles
and contrast checks determine where those colors can be used legibly.

## Historical references

The mapping was confirmed for this project. Historical systems offered multiple
schemes: these presets represent the named scheme, not every installation of
that operating system. Some colors are deliberately adjusted for JWM readability.

| Preset | Reference | Interpretation |
| --- | --- | --- |
| Redmond | Windows XP Luna Blue | Blue caption/panel, cream controls, white menus, blue selection; Flat/rounded frame. |
| Redmond Silver | Windows XP Luna Metallic | Silver/lavender caption and panel, pale controls, white menus and blue selection. |
| Redmond Olive | Windows XP Luna Homestead | Olive caption/panel, cream controls, sage selection with readable dark text. |
| Mountain View | SGI IRIX / Indigo Magic, brown-grey recreation | Warm grey active caption, grey inactive frame, slate selection and Motif relief. |
| Palo Alto | HP VUE / BroicaVUE adaptation | Peach active caption, slate inactive caption, mauve panel and rose menu. |
| Santa Clara | Solaris/CDE / Broica adaptation | Apricot active caption, grey inactive caption, sand panel and rose menu. |
| Austin | OS/2 Presentation Manager / Warp-inspired | Navy active caption/selection and grey controls; a visual adaptation, without an extracted IBM palette. |

### Sources and provenance

Original open CDE palette data:

- [CDE Broica.dp](https://github.com/cdesktopenv/cde/blob/d35c607e3a722201c6cd3213491a9483d40ef13e/cde/programs/palettes/Broica.dp).
  Its eight 16-bit RGB color sets supply the CDE tones; the high byte of each
  channel is used for 8-bit JWM colors. Their assignment to JWM components is an
  adaptation, not a complete implementation of CDE's color-set machinery.

Community recreations used as secondary visual/palette references:

- [NsCDE BroicaVUE.dp](https://github.com/NsCDE/NsCDE/blob/2d26bbece7e9c0dbee31bfe23ebfc1e1c88792bd/data/palettes/BroicaVUE.dp), for the VUE color-set family.
- [sgi-enhanced](https://github.com/jujum4n/sgi-enhanced/tree/b7a02161f8e13da639d2ecff5735436c9f447d67), especially `colors/theme-colors.txt`, `themerc`, and title XPM color tables: active `#A59F80`, inactive `#808080`, black caption text. This is a recreation, not an original SGI scheme dump.
- [B00merang Windows XP](https://github.com/B00merang-Project/Windows-XP/tree/7637830906823af40a3cd7e7079be753d8b7d679): Luna, Metallic and Homestead GTK CSS for cream/silver surfaces and selection colors. JWM title gradients, panel colors and some text contrasts remain adaptations; Luna bitmap buttons are not reproduced.

These references describe the provenance of the colors, not a claim that all
values or shapes came directly from the original operating systems.

## Other collections

- **Original:** retain their familiar accents and dark surfaces; Classic Motif
  explicitly selects Motif instead of inheriting whatever decoration was loaded.
- **Modern:** calm light surfaces, neutral menus, clear selection and Flat frames.
- **Chromatic:** one coherent hue family; darker focused captions, lighter inactive
  captions and light menu surfaces prevent a uniform mid-tone wash.
- **Pastel Workstations:** lavender, sage, salmon and cream tones assigned to
  separate roles, with Motif relief. These are original CDE-inspired palettes,
  not stock Solaris/VUE schemes despite their evocative names.
- **Hacker:** Phosphor/Matrix use green, Amber Terminal amber, Cyberdeck cyan,
  Purple Haze violet and Red Alert red accents. Captions and panels remain dark;
  selection uses the luminous accent with contrasting text. Monospace reinforces
  the terminal reference without imposing a particular installed font.

The reference/description is available in the preset selector's tooltip. Tests
cover all 34 palettes, text contrast, decoration support, XML preservation and
existing custom styles. Real JWM parsing also checks the generated configuration.
