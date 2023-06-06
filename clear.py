import os
import shutil

if __name__ == "__main__":
    try:
        shutil.rmtree("workspace")
    except:
        print("Workspace Cannot Find.")

    try:
        os.remove("processed_trends.db")
    except:
        print("Database Cannot Find.")

    finally:
        print("Finish")
