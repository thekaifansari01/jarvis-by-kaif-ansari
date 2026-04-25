import os
import json
import time
from datetime import datetime
from pathlib import Path
from modules.logger import logger

class WorkspaceManager:
    def __init__(self, base_path="Data/Jarvis_Workspace"):
        self.base_path = Path(base_path).resolve()
        self.registry_file = self.base_path / "registry.json"
        
        self.creations_dir = self.base_path / "Creations"
        self.vault_dir = self.base_path / "Vault"
        self.temp_dir = self.base_path / "Temp"
        
        self._init_workspace()

    def _init_workspace(self):
        for directory in [self.creations_dir, self.vault_dir, self.temp_dir]:
            directory.mkdir(parents=True, exist_ok=True)
            
        if not self.registry_file.exists():
            self._save_registry({"files": []})
            logger.info("📁 Workspace & Registry Initialized.")
            
        self.cleanup_temp()
        self.sync_registry()

    def _load_registry(self):
        try:
            with open(self.registry_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {"files": []}

    def _save_registry(self, data):
        with open(self.registry_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)

    def _get_safe_filename(self, directory, filename):
        base_name, ext = os.path.splitext(filename)
        counter = 1
        safe_name = filename
        while (directory / safe_name).exists():
            safe_name = f"{base_name} ({counter}){ext}"
            counter += 1
        return safe_name

    def _is_safe_path(self, directory, filename):
        try:
            target_path = (directory / Path(filename)).resolve()
            return str(target_path).startswith(str(directory.resolve()))
        except Exception:
            return False

    def sync_registry(self):
        registry = self._load_registry()
        existing_records = {f["filename"]: f for f in registry.get("files", [])}
        
        valid_files = []
        changed = False
        
        for folder_name, folder_path in [("Creations", self.creations_dir), 
                                         ("Vault", self.vault_dir), 
                                         ("Temp", self.temp_dir)]:
            for file_path in folder_path.iterdir():
                if file_path.is_file() and file_path.name != "registry.json":
                    filename = file_path.name
                    if filename not in existing_records:
                        valid_files.append({
                            "filename": filename,
                            "location": folder_name,
                            "description": "Manually added to workspace",
                            "added_on": datetime.now().strftime("%Y-%m-%d %H:%M")
                        })
                        changed = True
                        logger.info(f"🔄 Auto-Detected new file: {filename}")
                    else:
                        valid_files.append(existing_records[filename])
                        del existing_records[filename]

        if existing_records:
            changed = True
            logger.info(f"🧹 Removed {len(existing_records)} ghost files from registry.")

        if changed:
            self._save_registry({"files": valid_files})
            logger.info("🔄 Workspace Two-Way Sync Complete.")

    def cleanup_temp(self):
        now = time.time()
        cleaned = False
        for file_path in self.temp_dir.iterdir():
            if file_path.is_file():
                if now - file_path.stat().st_mtime > 86400:
                    file_path.unlink()
                    cleaned = True
        if cleaned:
            logger.info("🧹 Temp folder Auto-Cleaned (24h+ old files removed).")

    def get_storage_status(self):
        total_bytes = sum(f.stat().st_size for f in self.base_path.glob('**/*') if f.is_file())
        gb_size = total_bytes / (1024 ** 3)
        return f"{gb_size:.4f} GB / 10.00 GB Used"

    def add_file_record(self, filename, folder_name, description):
        registry = self._load_registry()
        existing = next((item for item in registry["files"] if item["filename"] == filename), None)
        
        record = {
            "filename": filename,
            "location": f"/{folder_name}",
            "description": description,
            "added_on": datetime.now().strftime("%Y-%m-%d %H:%M")
        }
        
        if existing:
            existing.update(record)
        else:
            registry["files"].append(record)
            
        self._save_registry(registry)
        logger.info(f"📓 Registry Updated: {filename} in {folder_name}")

    def get_safe_filepath(self, folder_name, original_filename):
        if folder_name.lower() == "creations":
            target_dir = self.creations_dir
        elif folder_name.lower() == "temp":
            target_dir = self.temp_dir
        else:
            target_dir = self.vault_dir
            
        if not self._is_safe_path(target_dir, original_filename):
            logger.error(f"🚨 Security Alert: Path Traversal blocked for {original_filename}")
            return None, None
            
        safe_name = self._get_safe_filename(target_dir, original_filename)
        return target_dir / safe_name, safe_name

    def find_file_in_workspace(self, filename: str) -> Path | None:
        """
        Search for a file by name across all workspace folders (Creations, Vault, Temp).
        Returns Path object if found, else None.
        Removes any leading slashes or folder prefixes.
        """
        if not filename:
            return None
        # Clean the filename: remove any path separators and take the base name
        clean_name = filename.strip("/\\").split("/")[-1].split("\\")[-1]
        for folder in [self.creations_dir, self.vault_dir, self.temp_dir]:
            candidate = folder / clean_name
            if candidate.exists():
                return candidate
        return None

    def list_files(self) -> str:
        """
        Returns a formatted string of all files in workspace with their locations.
        Useful for agentic loop's workspace_action list.
        """
        return self.get_workspace_context()

    def get_workspace_context(self):
        self.sync_registry()
        storage_info = self.get_storage_status()
        registry = self._load_registry()
        
        if not registry.get("files"):
            return f"[Storage: {storage_info}] Workspace is currently empty."
        
        context = [f"[Storage: {storage_info}]"]
        for f in registry["files"]:
            context.append(f"- {f['filename']} (in {f['location']}): {f['description']}")
            
        return "\n".join(context)

# Global instance
workspace = WorkspaceManager()