from core.monitor import InterviewMonitor


def main():
    print("Interview Monitor")
    print("-" * 45)
    print("Press 'q' to quit")
    print("-" * 45)

    monitor = InterviewMonitor()
    monitor.run()


if __name__ == "__main__":
    main()
