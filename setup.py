from pathlib import Path
from shutil import copytree
from urllib.request import urlopen
from zipfile import ZipFile
from io import BytesIO

from setuptools import setup
from setuptools.command.build_py import build_py as _build_py


STATIC_URLS = {
    "sprintf.js": "https://raw.githubusercontent.com/alexei/sprintf.js/1.1.2/dist/sprintf.min.js",
    "jquery.js": "https://code.jquery.com/jquery-3.6.0.min.js",
    "superfish/css/megafish.css": "https://raw.githubusercontent.com/joeldbirch/superfish/v1.7.10/dist/css/megafish.css",
    "superfish/css/superfish.css": "https://raw.githubusercontent.com/joeldbirch/superfish/v1.7.10/dist/css/superfish.css",
    "superfish/css/superfish-navbar.css": "https://raw.githubusercontent.com/joeldbirch/superfish/v1.7.10/dist/css/superfish-navbar.css",
    "superfish/css/superfish-vertical.css": "https://raw.githubusercontent.com/joeldbirch/superfish/v1.7.10/dist/css/superfish-vertical.css",
    "superfish/js/superfish.js": "https://raw.githubusercontent.com/joeldbirch/superfish/v1.7.10/dist/js/superfish.min.js",
    "superfish/js/hoverIntent.js": "https://raw.githubusercontent.com/joeldbirch/superfish/v1.7.10/dist/js/hoverIntent.js",
}


class build_py(_build_py):
    def run(self):
        super().run()
        package_dir = Path(self.build_lib) / "condo_suite"
        for directory in ("config", "handlers", "modules", "util", "templates", "resource"):
            copytree(Path("src") / directory, package_dir / directory, dirs_exist_ok=True)
        resource_dir = package_dir / "resource"
        for relative_path, url in STATIC_URLS.items():
            destination = resource_dir / relative_path
            if not destination.exists():
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(urlopen(url).read())

        archives = {
            "jquery-ui": (
                "https://jqueryui.com/resources/download/jquery-ui-1.13.1.zip",
                {
                    "jquery-ui.min.css": "jquery-ui/main.css",
                    "jquery-ui.structure.min.css": "jquery-ui/structure.css",
                    "jquery-ui.theme.min.css": "jquery-ui/theme.css",
                    "jquery-ui.min.js": "jquery-ui/main.js",
                },
                "images",
            ),
            "jquery-notify": (
                "https://github.com/vincentkeizer/notify/zipball/0.4.4",
                {"notify.min.css": "jquery-notify/main.css", "jquery-notify.min.js": "jquery-notify/main.js"},
                None,
            ),
            "readmore": (
                "https://github.com/jedfoster/Readmore.js/archive/refs/tags/2.2.1.zip",
                {"readmore.min.js": "readmore/main.js"},
                None,
            ),
            "append-grid": (
                "https://github.com/hkalbertl/jquery.appendGrid/archive/refs/tags/1.4.2.zip",
                {"jquery.appendGrid-1.4.2.min.css": "jquery-appendGrid/main.css",
                 "jquery.appendGrid-1.4.2.min.js": "jquery-appendGrid/main.js"},
                None,
            ),
        }
        for archive_name, (url, files, image_directory) in archives.items():
            missing = [target for source, target in files.items() if not (resource_dir / target).exists()]
            needs_images = image_directory and not (resource_dir / archive_name / image_directory).is_dir()
            if missing or needs_images:
                with ZipFile(BytesIO(urlopen(url).read())) as archive:
                    members = archive.namelist()
                    prefix = members[0].split("/", 1)[0]
                    for source, target in files.items():
                        destination = resource_dir / target
                        if not destination.exists():
                            destination.parent.mkdir(parents=True, exist_ok=True)
                            destination.write_bytes(archive.read("%s/%s" % (prefix, source)))
                    if needs_images:
                        image_prefix = "%s/%s/" % (prefix, image_directory)
                        for member in members:
                            if member.startswith(image_prefix) and not member.endswith("/"):
                                target = resource_dir / archive_name / image_directory / member[len(image_prefix):]
                                if not target.exists():
                                    target.parent.mkdir(parents=True, exist_ok=True)
                                    target.write_bytes(archive.read(member))


setup(
    packages=["condo_suite"],
    package_dir={"condo_suite": "src"},
    cmdclass={"build_py": build_py},
)
