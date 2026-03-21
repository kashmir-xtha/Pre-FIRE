import pandas as pd
import matplotlib.pyplot as plt
import os

# File list
files = [
    'data/simulation_history/simulation_history_20260320_174524.csv',
    'data/simulation_history/simulation_history_20260320_174736.csv',
    'data/simulation_history/simulation_history_20260320_175038.csv'
]

def generate_separate_plots():
    # Style settings to match dashboard
    plt.style.use('dark_background')
    fig_color = '#0e1117'
    ax_color = '#171b26'
    text_color = '#dde1ec'
    muted_color = '#6e7898'
    sim_colors = ['#3d8ef0', '#e05c2c', '#22a876']

    # List of individual metrics to plot (Column, Title, Y-Axis Label)
    metrics = [
        ('fire_cells', 'Fire Spread Analysis', 'Number of Burning Cells'),
        ('avg_temp', 'Average Temperature Profile', 'Temperature (C)'),
        ('avg_smoke', 'Smoke Density Evolution', 'Smoke Index'),
        ('path_length', 'Agent Path Progression', 'Remaining Steps')
    ]

    for col, title, ylabel in metrics:
        plt.figure(figsize=(10, 6), facecolor=fig_color)
        ax = plt.gca()
        ax.set_facecolor(ax_color)
        
        for idx, f in enumerate(files):
            if os.path.exists(f):
                df = pd.read_csv(f)
                plt.plot(df['time'], df[col], label=f'Sim {idx+1}', color=sim_colors[idx], linewidth=2)
        
        plt.title(title, color=text_color, fontsize=14, loc='left', pad=15)
        plt.xlabel('Time (s)', color=muted_color)
        plt.ylabel(ylabel, color=muted_color)
        plt.grid(True, color='gray', linestyle='--', alpha=0.1)
        plt.legend(frameon=False)
        plt.tight_layout()
        
        # Save each metric as a separate file
        filename = f"plot_{col}.png"
        plt.savefig(filename, facecolor=fig_color)
        print(f"Generated: {filename}")
        plt.close()

    # Special handling for Agent Health (Separate Plot)
    plt.figure(figsize=(10, 6), facecolor=fig_color)
    ax = plt.gca()
    ax.set_facecolor(ax_color)
    
    for idx, f in enumerate(files):
        if os.path.exists(f):
            df = pd.read_csv(f)
            # Split health data (e.g., "100.0T100.0T95.0") into separate agent columns
            health_df = df['agent_health'].str.split('T', expand=True).astype(float)
            for agent_idx in range(health_df.shape[1]):
                # Only add Sim label once per simulation group for the legend
                label = f'Sim {idx+1}' if agent_idx == 0 else None
                plt.plot(df['time'], health_df[agent_idx], color=sim_colors[idx], alpha=0.5, label=label)
    
    plt.title('Agent Health Performance', color=text_color, fontsize=14, loc='left', pad=15)
    plt.xlabel('Time (s)', color=muted_color)
    plt.ylabel('Health (%)', color=muted_color)
    plt.ylim(0, 105)
    plt.grid(True, color='gray', linestyle='--', alpha=0.1)
    plt.legend(frameon=False)
    plt.tight_layout()
    plt.savefig("plot_agent_health" + str(agent_idx + 1) + ".png", facecolor=fig_color)
    print("Generated: plot_agent_health" + str(agent_idx + 1) + ".png")
    plt.close()

if __name__ == "__main__":
    generate_separate_plots()