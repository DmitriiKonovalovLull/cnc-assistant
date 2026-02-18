# Regional Standards Structure

This directory contains standards organized by region.

## Structure

```
standards/
    ru/          # Russia: ГОСТ, ОСТ
    eu/          # Europe: EN, DIN, ISO
    cn/          # China: GB, GB/T
    storage/     # Uploaded PDF files
```

## Region Mapping

### Russia (RU)
- **ГОСТ** - State Standards
- **ОСТ** - Industry Standards

### Europe (EU)
- **EN** - European Norms
- **DIN** - German Standards
- **ISO** - International Standards (also available in other regions)

### China (CN)
- **GB** - National Standards
- **GB/T** - Recommended National Standards

## File Naming Convention

Standards are stored as:
```
{region}/{family}/{code}_{hash}.pdf
```

Example:
- `ru/GOST/7798-30_a1b2c3d4.pdf`
- `eu/DIN/912-88_e5f6g7h8.pdf`
- `cn/GB/T/5780-2000_i9j0k1l2.pdf`

## Usage

The `RegionResolver` automatically determines the user's region based on:
1. Explicit user preference
2. Standard family in request
3. Interface language
4. Default: Russia

Standards are filtered by region to ensure users only see relevant standards for their market.
