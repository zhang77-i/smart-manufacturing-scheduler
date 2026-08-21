import matplotlib.pyplot as plt


def plot_gantt(schedule):
    fig, ax = plt.subplots(figsize=(10, 5))

    for task in schedule:
        ax.barh(
            task["machine"],
            task["duration"],
            left=task["start"],
        )
        ax.text(
            task["start"],
            task["machine"],
            task["job"],
        )

    ax.set_xlabel("Time")
    ax.set_ylabel("Machine")
    ax.set_title("Production Schedule")

    return fig
