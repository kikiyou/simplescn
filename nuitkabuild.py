#! /usr/bin/env python3
import sys
import subprocess

if __name__ == "__main__":
    execute = ["/usr/bin/nuitka", "--recurse-all", "--recurse-stdlib", "--show-progress"]
    if "--standalone" in sys.argv:
        execute.append("--standalone")

    if "--backend=clang" in sys.argv:
        execute.append("--clang")
    elif "--backend=mingw" in sys.argv:
        execute.append("--mingw")

    if "--standalone" in sys.argv:
        execute.append("--standalone")
    if "--no-gui" not in sys.argv:
        try:
            import gi
            execute.append("--recurse-to=gi")
        except ImportError:
            pass
    if "--no-markdown" not in sys.argv:
        try:
            import markdown
            execute.append("--recurse-to=markdown")
        except ImportError:
            pass
    execute.append("./simplescn/__main__.py")
    with subprocess.Popen(execute, stdout=sys.stdout, stderr=sys.stderr, universal_newlines=True) as proc:
        proc.wait()
    
    
