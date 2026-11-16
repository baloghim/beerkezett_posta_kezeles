from .main import main as application_main


def main():
    return application_main(viewer=True)


if __name__ == "__main__":
    raise SystemExit(main())
