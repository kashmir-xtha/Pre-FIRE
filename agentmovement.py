import pygame
from queue import PriorityQueue

# Colors (kept local to avoid circular imports)
ORANGE = (255, 165, 0)
TURQUOISE = (64, 224, 208)
PURPLE = (128, 0, 128)
BLACK = (0, 0, 0)

# ------------------ HEURISTIC ------------------
def heuristic(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


# ------------------ PATH RECONSTRUCTION ------------------
def reconstruct_path(came_from, current, draw):
    while current in came_from:
        current = came_from[current]
        current.color = PURPLE
        draw()


# ------------------ A* ALGORITHM ------------------
def a_star(draw, grid, start, end, rows):
    count = 0
    open_set = PriorityQueue()
    open_set.put((0, count, start))

    came_from = {}
    g_score = {spot: float("inf") for row in grid for spot in row}
    f_score = {spot: float("inf") for row in grid for spot in row}

    g_score[start] = 0
    f_score[start] = heuristic(
        (start.row, start.col),
        (end.row, end.col)
    )

    open_set_hash = {start}

    while not open_set.empty():

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                return False

        current = open_set.get()[2]
        open_set_hash.remove(current)

        if current == end:
            reconstruct_path(came_from, end, draw)
            end.make_end()
            return True

        # 4-connected grid
        for dr, dc in [(1,0), (-1,0), (0,1), (0,-1)]:
            r = current.row + dr
            c = current.col + dc

            if 0 <= r < rows and 0 <= c < rows:
                neighbor = grid[r][c]

                if neighbor.color == BLACK:
                    continue

                temp_g = g_score[current] + 1

                if temp_g < g_score[neighbor]:
                    came_from[neighbor] = current
                    g_score[neighbor] = temp_g
                    f_score[neighbor] = temp_g + heuristic(
                        (r, c), (end.row, end.col)
                    )

                    if neighbor not in open_set_hash:
                        count += 1
                        open_set.put((f_score[neighbor], count, neighbor))
                        open_set_hash.add(neighbor)
                        neighbor.color = ORANGE

        draw()

        if current != start:
            current.color = TURQUOISE

    return False
