"""The CLAID notebook, transcribed verbatim as a Python script.

IPython magics (``%...``), shell escapes (``!...``) and bare ``pip install`` lines
are comments so the file parses as Python - nothing else was changed.  Some cells
need optional packages (igraph) or Colab paths, so this file records the original
study code; run claid_workflow.py to actually execute it.
"""

# CLAID notebook, verbatim transcription (30 cells)


# % [cell 00] code
# pip install igraph   (run once: python -m pip install igraph)
import igraph as ig

# % [cell 01] code
import pandas as pd
import networkx as nx
from networkx.algorithms import community
import community as community_louvain
import matplotlib.pyplot as plt
import igraph as ig
# %matplotlib inline  -> handled by the 'Agg' backend in the preamble

# % [cell 02] code
G = nx.karate_club_graph()

# % [cell 03] code
# Define the graph G
G = nx.karate_club_graph()

# Draw the graph
nx.draw_networkx(G)

# % [cell 04] md
# # Community Algorithms

# % [cell 05] md
# ## Edge betweenness (Girvan–Newman)

# % [cell 06] code
lst_b = nx.algorithms.community.girvan_newman(G)
type(lst_b)

# % [cell 07] code
for x in lst_b:
  print(x)

# % [cell 08] code
colors = ["#00C98D", "#5030C0", "#50F0F0"]
pos = nx.spring_layout(G)
lst_b = community.girvan_newman(G)
color_map_b = {}
keys = G.nodes()
values = "black"
for i in keys:
        color_map_b[i] = values
counter = 0
for x in lst_b:
  print(1)
  for c in x:
    for n in c:
      color_map_b[n] = colors[counter]
    counter = counter + 1
  break
nx.draw_networkx_edges(G, pos)
nx.draw_networkx_nodes(G, pos, node_color=dict(color_map_b).values())
nx.draw_networkx_labels(G, pos)
plt.axis("off")
plt.show()

# % [cell 09] code
modularity = []
for x in lst_b:
  modularity.append(community.modularity(G, x))
modularity

# % [cell 10] code
plt.plot(modularity, 'o')
plt.xlabel('# of clusters')
plt.ylabel('modularity')
plt.show()

# % [cell 11] code
max_modularity = max(modularity)
max_community = None

for community, mod_value in zip(lst_b, modularity):
    if mod_value == max_modularity:
        max_community = community
        break  # Stop after finding the maximum modularity community

if max_community:
    # Community visualization for the max_community
    colors = ["#00C98D", "#5030C0", "#50F0F0", 'red', 'blue']
    pos = nx.spring_layout(G)
    color_map_b = {}
    keys = G.nodes()
    values = "black"
    for i in keys:
        color_map_b[i] = values
    counter = 0
    for x in max_community:
        for n in x:
            color_map_b[n] = colors[counter]
        counter = counter + 1

    nx.draw_networkx_edges(G, pos)
    nx.draw_networkx_nodes(G, pos, node_color=dict(color_map_b).values())
    nx.draw_networkx_labels(G, pos)
    plt.axis("off")
    plt.show()
else:
    print("No community found with maximum modularity.")


# % [cell 12] md
# ## Modularity maximization

# % [cell 13] code
community.greedy_modularity_communities(G)

# % [cell 14] code
#Community visualization
colors = ["#00C98D", "#5030C0", "#50F0F0"]
pos = nx.spring_layout(G)
lst_b = community.greedy_modularity_communities(G)
color_map_b = {}
keys = G.nodes()
values = "black"
for i in keys:
        color_map_b[i] = values
counter = 0
for x in lst_b:
  for n in x:
    color_map_b[n] = colors[counter]
  counter = counter + 1

nx.draw_networkx_edges(G, pos)
nx.draw_networkx_nodes(G, pos, node_color=dict(color_map_b).values())
nx.draw_networkx_labels(G, pos)
plt.axis("off")
plt.show()

# % [cell 15] md
# ## Label propagation

# % [cell 16] code
colors = ["#00C98D", "#5030C0", "#50F0F0"]
pos = nx.spring_layout(G)
lst_m = community.label_propagation_communities(G)
color_map_b = {}
keys = G.nodes()
values = "black"
for i in keys:
        color_map_b[i] = values
counter = 0
for c in lst_m:
  for n in c:
    color_map_b[n] = colors[counter]
  counter = counter + 1
nx.draw_networkx_edges(G, pos)
nx.draw_networkx_nodes(G, pos, node_color=dict(color_map_b).values())
nx.draw_networkx_labels(G, pos)
plt.axis("off")
plt.show()

# % [cell 17] md
# ## Fast community unfolding (Louvian)

# % [cell 18] md
# Local moving of nodes: In this phase, each node is moved to the community that results in the highest increase in modularity. The node will remain in the same community if there is no positive gain. This process is applied repeatedly and for all nodes until no further improvement is possible. The first phase of the Louvain algorithm stops when a local maximum of modularity is obtained.
#
#
# Building a new network: In this phase, the algorithm builds a new network considering communities found in the first phase as nodes. The weights of the links between communities are the sum of the weights of the links between their nodes. Once the second phase is completed, the algorithm will reapply the first phase to the resulting network. These steps are repeated until there are no changes in the network and maximum modularity is obtained
#

# % [cell 19] code
# pip install community   (run once: python -m pip install community)

# % [cell 20] code
import networkx as nx
from community import community_louvain
import matplotlib.pyplot as plt

# Assuming G is defined and has nodes and edges added to it
G = nx.Graph()

# Generate a sample graph for demonstration
G.add_edges_from([(1, 2), (2, 3), (3, 4), (4, 1)])

colors = ["#00C98D", "#5030C0", "#50F0F0", 'yellow']
pos = nx.spring_layout(G)
lst_m = community_louvain.best_partition(G)
color_map_b = {}
keys = G.nodes()
values = "black"
for i in keys:
        color_map_b[i] = values

for n in dict(lst_m):
  color_map_b[n] = colors[lst_m[n]]

plt.figure(figsize=(8, 8))  # Increase the figure size
nx.draw_networkx_edges(G, pos)
nx.draw_networkx_nodes(G, pos, node_color=dict(color_map_b).values())
nx.draw_networkx_labels(G, pos)
plt.axis("off")
plt.show()


# % [cell 21] code
import requests
from bs4 import BeautifulSoup
import networkx as nx
import matplotlib.pyplot as plt

# Function to scrape data from a website
def scrape_website(url):
    try:
        response = requests.get(url)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            # Extract relevant data from the website
            # Example: titles, links, text, etc.
            # For simplicity, let's extract text content
            text_content = soup.get_text()
            return text_content
        else:
            print("Failed to retrieve data from:", url)
            return None
    except Exception as e:
        print("Error occurred:", e)
        return None

# Main function for network analysis
def main():
    # Define the URL to scrape
    url = "https://example.com"

    # Scrape data from the website
    text_content = scrape_website(url)

    # If data is successfully scraped, perform network analysis
    if text_content:
        # Create a graph
        G = nx.Graph()

        # Process text content (you may need more advanced text processing here)
        # For simplicity, let's split text by whitespace
        words = text_content.split()

        # Add nodes and edges to the graph
        for i in range(len(words) - 1):
            word1 = words[i]
            word2 = words[i + 1]
            if not G.has_edge(word1, word2):
                G.add_edge(word1, word2)

        # Visualize the network
        pos = nx.spring_layout(G)
        plt.figure(figsize=(10, 10))
        nx.draw(G, pos, with_labels=True, node_color='skyblue', node_size=1000, edge_color='black', linewidths=1, font_size=15)
        plt.title("Website Network Analysis")
        plt.show()
    else:
        print("Failed to scrape data. Exiting...")

if __name__ == "__main__":
    main()


# % [cell 22] code
# pip install Flask   (run once: python -m pip install Flask)


# % [cell 23] md
# ## **final **

# % [cell 24] code
# pip install igraph   (run once: python -m pip install igraph)
import igraph as ig
import pandas as pd
import networkx as nx
from networkx.algorithms import community
import community as community_louvain
import matplotlib.pyplot as plt
import igraph as ig
# %matplotlib inline  -> handled by the 'Agg' backend in the preamble
G = nx.karate_club_graph()
# Define the graph G
G = nx.karate_club_graph()

# Draw the graph
nx.draw_networkx(G)
lst_b = nx.algorithms.community.girvan_newman(G)
type(lst_b)
for x in lst_b:
  print(x)
colors = ["#00C98D", "#5030C0", "#50F0F0"]
pos = nx.spring_layout(G)
lst_b = community.girvan_newman(G)
color_map_b = {}
keys = G.nodes()
values = "black"
for i in keys:
        color_map_b[i] = values
counter = 0
for x in lst_b:
  print(1)
  for c in x:
    for n in c:
      color_map_b[n] = colors[counter]
    counter = counter + 1
  break
nx.draw_networkx_edges(G, pos)
nx.draw_networkx_nodes(G, pos, node_color=dict(color_map_b).values())
nx.draw_networkx_labels(G, pos)
plt.axis("off")
plt.show()
modularity = []
for x in lst_b:
  modularity.append(community.modularity(G, x))
modularity
plt.plot(modularity, 'o')
plt.xlabel('# of clusters')
plt.ylabel('modularity')
plt.show()
max_modularity = max(modularity)
max_community = None

for community, mod_value in zip(lst_b, modularity):
    if mod_value == max_modularity:
        max_community = community
        break  # Stop after finding the maximum modularity community

if max_community:
    # Community visualization for the max_community
    colors = ["#00C98D", "#5030C0", "#50F0F0", 'red', 'blue']
    pos = nx.spring_layout(G)
    color_map_b = {}
    keys = G.nodes()
    values = "black"
    for i in keys:
        color_map_b[i] = values
    counter = 0
    for x in max_community:
        for n in x:
            color_map_b[n] = colors[counter]
        counter = counter + 1

    nx.draw_networkx_edges(G, pos)
    nx.draw_networkx_nodes(G, pos, node_color=dict(color_map_b).values())
    nx.draw_networkx_labels(G, pos)
    plt.axis("off")
    plt.show()
else:
    print("No community found with maximum modularity.")
community.greedy_modularity_communities(G)
#Community visualization
colors = ["#00C98D", "#5030C0", "#50F0F0"]
pos = nx.spring_layout(G)
lst_b = community.greedy_modularity_communities(G)
color_map_b = {}
keys = G.nodes()
values = "black"
for i in keys:
        color_map_b[i] = values
counter = 0
for x in lst_b:
  for n in x:
    color_map_b[n] = colors[counter]
  counter = counter + 1

nx.draw_networkx_edges(G, pos)
nx.draw_networkx_nodes(G, pos, node_color=dict(color_map_b).values())
nx.draw_networkx_labels(G, pos)
plt.axis("off")
plt.show()
colors = ["#00C98D", "#5030C0", "#50F0F0"]
pos = nx.spring_layout(G)
lst_m = community.label_propagation_communities(G)
color_map_b = {}
keys = G.nodes()
values = "black"
for i in keys:
        color_map_b[i] = values
counter = 0
for c in lst_m:
  for n in c:
    color_map_b[n] = colors[counter]
  counter = counter + 1
nx.draw_networkx_edges(G, pos)
nx.draw_networkx_nodes(G, pos, node_color=dict(color_map_b).values())
nx.draw_networkx_labels(G, pos)
plt.axis("off")
plt.show()
# pip install community   (run once: python -m pip install community)
import networkx as nx
from community import community_louvain
import matplotlib.pyplot as plt

# Assuming G is defined and has nodes and edges added to it
G = nx.Graph()

# Generate a sample graph for demonstration
G.add_edges_from([(1, 2), (2, 3), (3, 4), (4, 1)])

colors = ["#00C98D", "#5030C0", "#50F0F0", 'yellow']
pos = nx.spring_layout(G)
lst_m = community_louvain.best_partition(G)
color_map_b = {}
keys = G.nodes()
values = "black"
for i in keys:
        color_map_b[i] = values

for n in dict(lst_m):
  color_map_b[n] = colors[lst_m[n]]

plt.figure(figsize=(8, 8))  # Increase the figure size
nx.draw_networkx_edges(G, pos)
nx.draw_networkx_nodes(G, pos, node_color=dict(color_map_b).values())
nx.draw_networkx_labels(G, pos)
plt.axis("off")
plt.show()

import requests
from bs4 import BeautifulSoup
import networkx as nx
import matplotlib.pyplot as plt

# Function to scrape data from a website
def scrape_website(url):
    try:
        response = requests.get(url)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            # Extract relevant data from the website
            # Example: titles, links, text, etc.
            # For simplicity, let's extract text content
            text_content = soup.get_text()
            return text_content
        else:
            print("Failed to retrieve data from:", url)
            return None
    except Exception as e:
        print("Error occurred:", e)
        return None

# Main function for network analysis
def main():
    # Define the URL to scrape
    url = "https://example.com"

    # Scrape data from the website
    text_content = scrape_website(url)

    # If data is successfully scraped, perform network analysis
    if text_content:
        # Create a graph
        G = nx.Graph()

        # Process text content (you may need more advanced text processing here)
        # For simplicity, let's split text by whitespace
        words = text_content.split()

        # Add nodes and edges to the graph
        for i in range(len(words) - 1):
            word1 = words[i]
            word2 = words[i + 1]
            if not G.has_edge(word1, word2):
                G.add_edge(word1, word2)

        # Visualize the network
        pos = nx.spring_layout(G)
        plt.figure(figsize=(10, 10))
        nx.draw(G, pos, with_labels=True, node_color='skyblue', node_size=1000, edge_color='black', linewidths=1, font_size=15)
        plt.title("Website Network Analysis")
        plt.show()
    else:
        print("Failed to scrape data. Exiting...")

if __name__ == "__main__":
    main()


# % [cell 25] code


# % [cell 26] code
import networkx as nx
import matplotlib.pyplot as plt
from sklearn.metrics import f1_score
from networkx.algorithms import community

# Assuming G is defined and has nodes and edges added to it
G = nx.Graph()

# Generate a sample graph for demonstration
G.add_edges_from([(1, 2), (2, 3), (3, 4), (4, 1)])

colors = ["#00C98D", "#5030C0", "#50F0F0", 'yellow']
pos = nx.spring_layout(G)
lst_m = community.greedy_modularity_communities(G)
color_map_b = {}
keys = G.nodes()
values = "black"
for i in keys:
        color_map_b[i] = values

# Assuming ground truth labels are available
ground_truth_labels = {1: 0, 2: 0, 3: 1, 4: 1}  # Example ground truth labels

predicted_labels = []
for node in G.nodes():
    for i, community in enumerate(lst_m):
        if node in community:
            predicted_labels.append(i)
            break

# Calculate F1 score
f1 = f1_score(list(ground_truth_labels.values()), predicted_labels, average='weighted')

print("F1 Score:", f1)

# Calculate betweenness centrality for each node within each community
betweenness_centralities = {}
for i, community in enumerate(lst_m):
    community_subgraph = G.subgraph(community)
    betweenness_centralities[i] = nx.betweenness_centrality(community_subgraph)

# Visualize the betweenness centrality for nodes within each community
for i, community in enumerate(lst_m):
    community_subgraph = G.subgraph(community)
    node_colors = [betweenness_centralities[i][node] for node in community_subgraph.nodes()]
    nx.draw_networkx_edges(G, pos)
    # Use plt.scatter() to create nodes and get a mappable object
    nodes = nx.draw_networkx_nodes(G, pos, node_color=node_colors, cmap=plt.cm.Blues)
    nx.draw_networkx_labels(G, pos)
    plt.title(f"Community {i} Betweenness Centrality")
    # Create colorbar using the mappable object returned by plt.scatter()
    plt.colorbar(nodes, label='Betweenness Centrality')
    plt.axis("off")
    plt.show()


# % [cell 27] md
# # Calculate centrality measures
# degree_centrality = nx.degree_centrality(G)
# betweenness_centrality = nx.betweenness_centrality(G)
# eigenvector_centrality = nx.eigenvector_centrality(G)
#
# # Identify anomalies based on centrality measures (you can adjust the threshold as needed)
# degree_threshold = 2 * sum(degree_centrality.values()) / len(degree_centrality)
# betweenness_threshold = 2 * sum(betweenness_centrality.values()) / len(betweenness_centrality)
# eigenvector_threshold = 2 * sum(eigenvector_centrality.values()) / len(eigenvector_centrality)
#
# anomaly_nodes = []
# for node in G.nodes():
#     if degree_centrality[node] > degree_threshold or \
#        betweenness_centrality[node] > betweenness_threshold or \
#        eigenvector_centrality[node] > eigenvector_threshold:
#         anomaly_nodes.append(node)
#
# # Draw the graph with anomalies highlighted
# plt.figure(figsize=(10, 10))
# pos = nx.spring_layout(G)
#
# # Draw normal nodes
# nx.draw(G, pos, nodelist=[n for n in G.nodes() if n not in anomaly_nodes],
#         with_labels=True, node_color='skyblue', node_size=1000,
#         edge_color='black', linewidths=1, font_size=15)
#
# # Draw anomaly nodes with different color and larger size
# nx.draw_networkx_nodes(G, pos, nodelist=anomaly_nodes, node_color='red', node_size=2000)
#
# # Draw edges
# nx.draw_networkx_edges(G, pos, alpha=0.5)
#
# plt.title("Network Graph with Anomalies")
# plt.show()
#

# % [cell 28] code
import pandas as pd
import networkx as nx
import community as community_louvain
import matplotlib.pyplot as plt
from sklearn.metrics import f1_score
# %matplotlib inline  -> handled by the 'Agg' backend in the preamble

# Read the dataset from the provided path
dataset_path = "/content/Dataset.csv"
df = pd.read_csv(dataset_path)

# Assuming the dataset contains columns 'source_node' and 'target_node' representing edges
# If your dataset has different column names, please replace them accordingly
G = nx.from_pandas_edgelist(df, 'source_node', 'target_node')

# Anomaly Detection using Degree Centrality
degree_centrality = nx.degree_centrality(G)

# Compute mean and standard deviation of degree centrality
mean_degree_centrality = sum(degree_centrality.values()) / len(degree_centrality)
std_degree_centrality = sum([(x - mean_degree_centrality) ** 2 for x in degree_centrality.values()]) / len(degree_centrality)
threshold = mean_degree_centrality + 2 * std_degree_centrality

# Identify anomalies
anomalies = {node: centrality for node, centrality in degree_centrality.items() if centrality > threshold}

# Draw the graph with adjusted parameters
plt.figure(figsize=(12, 12))
pos = nx.spring_layout(G, k=0.15)  # Adjust 'k' to increase spacing between clusters

# Draw edges with reduced width and gray color
nx.draw_networkx_edges(G, pos, edge_color='gray', width=0.5)

# Draw normal nodes with reduced size and light blue color
nx.draw_networkx_nodes(G, pos, nodelist=[node for node in G.nodes() if node not in anomalies],
                       node_color='lightblue', node_size=100, alpha=0.8)

# Highlight anomalies in red
nx.draw_networkx_nodes(G, pos, nodelist=anomalies.keys(), node_color='red', node_size=300)

# Hide node labels
nx.draw_networkx_labels(G, pos, labels={}, font_size=12)

plt.title("Network Graph with Anomalies")
plt.show()

# Convert anomalies to a DataFrame for easier analysis
anomalies_df = pd.DataFrame.from_dict(anomalies, orient='index', columns=['Degree Centrality'])

# Calculate F1 score (assuming you have ground truth for anomalies)
# ground_truth_anomalies should be a dictionary with node IDs as keys and anomaly labels as values
# For example: ground_truth_anomalies = {'node1': 1, 'node2': 0, ...}
# Adjust the threshold as needed based on your data and requirements
ground_truth_anomalies = {}  # Replace with actual ground truth if available
predicted_anomalies = {node: 1 if centrality > threshold else 0 for node, centrality in degree_centrality.items()}
y_true = [ground_truth_anomalies.get(node, 0) for node in G.nodes()]
y_pred = [predicted_anomalies.get(node, 0) for node in G.nodes()]
f1score = f1_score(y_true, y_pred)

print("F1 Score:", f1score)
print("Anomalies:")
print(anomalies_df)


# % [cell 29] code
import pandas as pd
import networkx as nx
from sklearn.metrics import precision_score, recall_score, f1_score
from networkx.algorithms import community as nx_comm

# Read the dataset
dataset = {
    'SOURCE_SUBREDDIT': ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H'],
    'TARGET_SUBREDDIT': ['B', 'C', 'D', 'A', 'F', 'G', 'H', 'E'],
    'Ground_Truth_Community': [0, 0, 1, 1, 2, 2, 3, 3]  # Example ground truth labels
}

# Convert dataset to DataFrame
df = pd.DataFrame(dataset)

# Create Graph
G = nx.from_pandas_edgelist(df, 'SOURCE_SUBREDDIT', 'TARGET_SUBREDDIT')

# Ground truth labels
ground_truth_labels = dict(zip(df['SOURCE_SUBREDDIT'], df['Ground_Truth_Community']))

# Community detection
lst_m = list(nx_comm.greedy_modularity_communities(G))

# Louvain modularity
partition = nx_comm.greedy_modularity_communities(G)

# Betweenness centrality
betweenness_centralities = nx.betweenness_centrality(G)

# Convert Louvain partition to node-community mapping
louvain_labels = {}
for i, comm in enumerate(partition):
    for node in comm:
        louvain_labels[node] = i

# Calculate precision, recall, and F1 score for each method
precision_community = precision_score(list(ground_truth_labels.values()), [ground_truth_labels[node] for node in G.nodes()], average='weighted')
recall_community = recall_score(list(ground_truth_labels.values()), [ground_truth_labels[node] for node in G.nodes()], average='weighted')
f1_community = f1_score(list(ground_truth_labels.values()), [ground_truth_labels[node] for node in G.nodes()], average='weighted')

precision_louvain = precision_score(list(ground_truth_labels.values()), [louvain_labels[node] for node in G.nodes()], average='weighted')
recall_louvain = recall_score(list(ground_truth_labels.values()), [louvain_labels[node] for node in G.nodes()], average='weighted')
f1_louvain = f1_score(list(ground_truth_labels.values()), [louvain_labels[node] for node in G.nodes()], average='weighted')

# Convert betweenness centrality scores to subreddit labels
betweenness_labels = {subreddit: max(betweenness_centralities, key=betweenness_centralities.get) for subreddit in ground_truth_labels.keys()}

# Calculate precision, recall, and F1 score for betweenness centrality
precision_betweenness = precision_score(list(ground_truth_labels.values()), [ground_truth_labels[node] for node in betweenness_labels.keys()], average='weighted')
recall_betweenness = recall_score(list(ground_truth_labels.values()), [ground_truth_labels[node] for node in betweenness_labels.keys()], average='weighted')
f1_betweenness = f1_score(list(ground_truth_labels.values()), [ground_truth_labels[node] for node in betweenness_labels.keys()], average='weighted')

# Tabulate the results
results = pd.DataFrame({
    'Method': ['Community Detection', 'Louvain Modularity', 'Betweenness Centrality'],
    'Precision': [precision_community, precision_louvain, precision_betweenness],
    'Recall': [recall_community, recall_louvain, recall_betweenness],
    'F1 Score': [f1_community, f1_louvain, f1_betweenness]
})

print(results)
