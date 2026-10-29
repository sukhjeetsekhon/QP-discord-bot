# Discord Message Formatting & Markdown Rules

This document outlines the official Discord message formatting capabilities, syntax rules, limitations, and styling best practices for the QP AI Assistant.

---

## 1. Supported Discord Formatting

Discord supports a specific subset of Markdown. When composing answers, use only the following supported styles:

### Text Styles
- **Bold**: `**text**` → **text**
- *Italics*: `*text*` or `_text_` → *text*
- ***Bold Italics***: `***text***` → ***text***
- __Underline__: `__text__` → __text__
- ~~Strikethrough~~: `~~text~~` → ~~text~~
- ||Spoiler||: `||text||` → Hidden until clicked

### Headers
- `# Large Header` (Header 1)
- `## Medium Header` (Header 2)
- `### Small Header` (Header 3 - recommended for subheadings)

### Lists
- **Unordered Bullet Points**:
  ```text
  - First item
  - Second item
    - Indented sub-item (2 spaces)
  ```
- **Ordered Numbered Lists**:
  ```text
  1. Step one
  2. Step two
  3. Step three
  ```

### Quotes & Callouts
- Single-line Quote: `> text`
- Multi-line Quote: `>>> text`

### Code Formatting
- **Inline Code**: `` `pinMode(13, OUTPUT);` ``
- **Syntax-Highlighted Code Blocks**:
  ````text
  ```cpp
  void setup() {
    Wire.begin();
  }
  ```
  ````
  Always specify the language tag (`cpp`, `python`, `bash`, `json`, `c`, `arduino`).

### Links
- **Masked Hyperlinks**: `[IEEE UCSD Website](https://ieeeucsd.org)`

---

## 2. STRICTLY PROHIBITED (Unsupported by Discord)

Discord **does NOT** render the following formatting. Never use them in AI responses:

| Feature | Does Discord Support It? | What Happens / What to Use Instead |
| :--- | :---: | :--- |
| **LaTeX / KaTeX Math** (`$2.2\text{ k}\Omega$`) | ❌ **NO** | Discord prints raw `$`, `\text{...}`, and `\Omega`. **Never use LaTeX.** Use plain text Unicode units (`2.2 kΩ`, `10 µF`). |
| **Markdown Tables** (`\| Col \| Col \|`) | ❌ **NO** | Renders as raw, unformatted pipe characters. **Never use tables.** Format tabular data as clean bulleted lists or key-value pairs instead. |
| **HTML Tags** (`<br>`, `<div>`, `<b>`) | ❌ **NO** | Rendered as raw text or stripped completely. Use standard Discord markdown only. |
| **Inline Markdown Images** (`![alt](url)`) | ❌ **NO** | Markdown image tags do not embed inline. |

---

## 3. Formatting Math, Units & Formulas (NO LaTeX!)

Discord **never** renders LaTeX math syntax. Dollar signs (`$`) and LaTeX macros (`\text{}`, `\Omega`, `\mu`, `\frac{}{}`) will print literally on Discord and look broken to users.

### Conversion Guide: LaTeX vs. Discord

| Type | ❌ Prohibited (LaTeX) | ✅ Allowed (Clean Discord Text) |
| :--- | :--- | :--- |
| **Resistors** | `$2.2\text{ k}\Omega$ to $3.3\text{ k}\Omega$` | `2.2 kΩ to 3.3 kΩ` or `2.2k to 3.3k ohm` |
| **Resistors (Ohms)** | `$10\text{ k}\Omega$` or `$4.7\text{k}\Omega$` | `10 kΩ` or `4.7 kΩ` |
| **Capacitors** | `$10\mu\text{F}$` or `$100\text{nF}$` | `10 µF` or `100 nF` |
| **Voltages** | `$V_{in} = 5\text{V}$` or `$3.3\text{V}$` | `Vin = 5V` or `3.3V` |
| **Tolerances** | `$\pm 5\%$` | `±5%` |
| **Approximations** | `$\approx 100\text{ mA}$` | `≈ 100 mA` |
| **Temperatures** | `$25\degree\text{C}$` or `$25^\circ\text{C}$` | `25°C` |
| **Equations** | `$f = \frac{1}{2\pi RC}$` | `f = 1 / (2π * R * C)` |
| **Variables** | `$R_1$`, `$C_1$`, `$I_{max}$` | `R1`, `C1`, `I_max` |

> [!IMPORTANT]
> The dollar sign (`$`) must **ONLY** be used when describing money and budgets (e.g. `$50.00 base budget`, `$11.00 bonus`). Never wrap equations, numbers, or units in dollar signs.

---

## 4. Formatting Tabular Data Without Tables

Instead of an unrendered markdown table like:
```text
| Component | Pin on Arduino |
| OLED SDA  | Pin A4         |
| OLED SCL  | Pin A5         |
```
**Always use bullet points or key-value format:**
```text
• **OLED SDA** → Analog Pin `A4` (or dedicated SDA pin near AREF)
• **OLED SCL** → Analog Pin `A5` (or dedicated SCL pin near AREF)
• **OLED VCC** → `5V` (or `3.3V` depending on the module)
• **OLED GND** → `GND`
```

---

## 5. Discord Character Limits & Chunking Best Practices

1. **2,000 Character Hard Limit**:
   - A single Discord message cannot exceed 2,000 characters.
   - Aim for responses between **800 and 1,500 characters** so answers fit cleanly in a single message without needing to split.

2. **Concise Code Snippets**:
   - Do **NOT** paste 100 lines of full boilerplate sketch code.
   - Provide only the **critical 10–20 lines** demonstrating the exact wiring initialization, pin definitions, or library call.
   - Large code blocks easily cross message boundaries and degrade mobile readability.

3. **Code Block Closure Safety**:
   - Every code block opened with triple backticks (` ``` `) must be closed with triple backticks (` ``` `).
   - Never leave unclosed code blocks or split open syntax tags across message boundaries.
