# Discord Message Formatting & Markdown Rules

This document outlines the official Discord message formatting capabilities, syntax rules, limitations, and styling best practices for the QP AI Assistant.

---

## 1. Supported Discord Formatting

Discord supports a subset of Markdown. When composing answers, use only the following supported styles:

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
| **Markdown Tables** (`\| Col \| Col \|`) | ❌ **NO** | Renders as raw, unformatted pipe characters. **Never use tables.** Format tabular data as clean bulleted lists or key-value pairs instead. |
| **HTML Tags** (`<br>`, `<div>`, `<b>`) | ❌ **NO** | Rendered as raw text or stripped completely. Use standard Discord markdown only. |
| **LaTeX / KaTeX Math** (`$E = mc^2$`) | ❌ **NO** | Dollar signs render as raw text. Use standard Unicode symbols instead (e.g. `Ω`, `µF`, `±`, `°C`, `V`, `A`). |
| **Inline Markdown Images** (`![alt](url)`) | ❌ **NO** | Markdown image tags do not embed inline. |

### How to Format Tabular Data Without Tables
Instead of a markdown table like:
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

## 3. Discord Character Limits & Chunking Best Practices

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
