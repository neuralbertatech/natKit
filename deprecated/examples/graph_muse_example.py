import natKit


def main():
    muse_connection = natKit.connect("Muse-2")
    graph = natKit.create_raw_graph()
    pipeline = natKit.pipeline_builder([muse_connection, graph])
    pipeline.start()


if __name__ == "__main__":
    main()
