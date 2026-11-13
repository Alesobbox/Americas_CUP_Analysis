"""One-time safe reorganizer for Data/AC37/ files into semantic directories."""
import os
from pathlib import Path
import shutil

def main():
    root = Path(__file__).resolve().parents[1]
    ac37_root = root / "Data" / "AC37"
    if not ac37_root.exists():
        print(f"Error: {ac37_root} does not exist!")
        return

    mapping = []

    # 1. Loose files in Data/AC37 (2023 AC40 prelims)
    for f in sorted(ac37_root.glob("*.jsonl")):
        mapping.append((f, ac37_root / "prelims_ac40_2023" / f.name))

    # 2. Files in JSON
    json_dir = ac37_root / "JSON"
    if json_dir.exists():
        for f in sorted(json_dir.glob("*.jsonl")):
            name = f.name
            if any(op in name for op in ("OP2", "OP3", "OP4", "OP6", "OP7")):
                target = ac37_root / "ac75_official_practice" / name
            elif "FPR" in name or "Preliminary" in name:
                target = ac37_root / "ac75_prelim_barcelona" / name
            elif "RR1" in name or "RR2" in name:
                target = ac37_root / "ac75_lvc_round_robins" / name
            else:
                target = ac37_root / "ac75_official_practice" / name
            mapping.append((f, target))

    # 3. Files in Public AC37 (Semifinals binary protobuf)
    pub_ac37 = ac37_root / "Public AC37"
    if pub_ac37.exists():
        for f in sorted(pub_ac37.glob("*")):
            if f.is_file():
                mapping.append((f, ac37_root / "ac75_lvc_semifinals_raw" / f.name))

    # 4. Files in Public JSON (Finals)
    pub_json = ac37_root / "Public JSON"
    if pub_json.exists():
        for f in sorted(pub_json.glob("*")):
            if f.is_file():
                mapping.append((f, ac37_root / "ac75_lvc_finals" / f.name))

    print(f"Moving {len(mapping)} files into structured directories...")
    moved_count = 0
    total_bytes = 0

    for src, dst in mapping:
        dst.parent.mkdir(parents=True, exist_ok=True)
        size = src.stat().st_size
        total_bytes += size
        shutil.move(str(src), str(dst))
        moved_count += 1

    print(f"Successfully moved {moved_count} files ({total_bytes / (1024**3):.2f} GB).")

    # Clean up empty source directories
    for old_dir in (json_dir, pub_ac37, pub_json):
        if old_dir.exists():
            remaining = list(old_dir.iterdir())
            if not remaining:
                old_dir.rmdir()
                print(f"Removed empty directory: {old_dir.name}")
            else:
                print(f"Warning: {old_dir.name} still contains {len(remaining)} items")

    # Final verification of structure
    print("\n=== Final Data/AC37 Structure ===")
    subdirs = sorted([d for d in ac37_root.iterdir() if d.is_dir()], key=lambda d: d.name)
    verified_files = 0
    verified_bytes = 0
    for d in subdirs:
        files = list(d.glob("*"))
        d_bytes = sum(f.stat().st_size for f in files)
        verified_files += len(files)
        verified_bytes += d_bytes
        print(f"  {d.name:30s}: {len(files):3d} files ({d_bytes / (1024*1024):8.1f} MB)")
    print(f"TOTAL: {verified_files} files, {verified_bytes / (1024**3):.2f} GB")


if __name__ == "__main__":
    main()
