
import json
import math
import gym
from gym.spaces import Space, Box, Discrete, Dict, Tuple, MultiBinary, MultiDiscrete
import minihack
from nle import nethack
from typing import Dict
from queue import PriorityQueue
import time
import sys
import numpy

numpy.set_printoptions(threshold=sys.maxsize)

env = gym.make('NetHackChallenge-v0', )


class GameWhisperer:

    def __init__(self, fast_mode):
        self.a_yx = [-1, -1]
        self.walkable_glyphs = [(33, -1), (34, -1), (35, 7), (35, 15), (36, -1), (37, -1), (40, -1), (41, -1), (42, -1),
                                (46, -1),
                                (47, -1), (45, 3), (60, -1), (61, -1), (62, -1), (63, -1), (64, 15), (91, -1), (92, -1),
                                (93, -1),
                                (96, -1), (100, 15), (100, 7), (102, 15), (102, 7), (117, -1), (124, 3)]
        self.size_y = 21
        self.size_x = 79
        self.current_obs = env.reset()
        self.glyph_obs = self.current_obs.__getitem__("glyphs")
        self.char_obs = self.current_obs.__getitem__("chars")
        self.color_obs = self.current_obs.__getitem__("colors")
        self.message = self.current_obs.__getitem__("message")
        self.parsed_message = self.parse_message()
        self.all_obs = self.current_obs.__getitem__("tty_chars")
        self.bl_stats = self.current_obs.__getitem__("blstats")
        self.memory = [[-1 for _ in range(self.size_x)] for _ in range(self.size_y)]
        self.exception = []
        self.search_map = [[0 for _ in range(self.size_x)] for _ in range(self.size_y)]
        self.risk_map = [[0 for _ in range(self.size_x)] for _ in range(self.size_y)]
        self.last_risk_update = 0
        self.act_num = 0
        self.score = 0
        self.total_score = 0
        self.cooldown = 100000
        self.default_search_max = 10
        self.default_hard_search_max = 10
        self.search_max = self.default_search_max
        self.hard_search_max = self.default_hard_search_max
        self.agent_id = -1
        self.update_agent()
        self.agent_id = self.glyph_obs[self.a_yx[0]][self.a_yx[1]]
        self.memory[self.a_yx[0]][self.a_yx[0]] = self.act_num
        self.safe_play = False
        self.strict_safe_play = False  # quando la strategia prevede la sicurezza pi?? categorica
        self.recently_ejected = False
        self.last_monster_searched = (-1, -1, 0)
        self.monster_exception = []
        self.engraved_tiles = []
        self.inedible = []
        self.recently_killed = []
        self.shop_tiles = []
        self.last_pray = -1
        self.old_turn = 0
        self.new_turn = 0
        self.panic = False
        self.pet_alive = False
        self.pet_alive_turn = 0
        self.ran = False
        self.ran_turn = 0
        self.ran_cooldown = 2
        self.guard_encounter = 0
        self.u_stairs_locations = []
        self.d_stairs_locations = []
        self.fast_mode = fast_mode
        self.stuck_counter = 0
        self.hard_search_num = 0
        #if not self.fast_mode:
            #env.render()

    def calculate_risk(self, y, x):
        touched = []
        layer = self.neighbors_8_dir(y, x)
        self.risk_map[y][x] += 2
        for tile in layer:
            self.risk_map[tile[0]][tile[1]] += 2
            touched.append((tile[0], tile[1]))

        for tile in layer:
            second_layer = self.neighbors_8_dir(tile[0], tile[1])
            for s_tile in second_layer:
                if not touched.__contains__((s_tile[0], s_tile[1])):
                    self.risk_map[s_tile[0]][s_tile[1]] += 1
                    touched.append((s_tile[0], s_tile[1]))

    # metodo per l'aggiornamento dell'osservazione dei pericoli
    def update_riskmap(self):
        self.risk_map = [[0 for _ in range(self.size_x)] for _ in range(self.size_y)]

        for y in range(self.size_y):
            for x in range(self.size_x):
                if self.is_a_monster(y, x):
                    self.calculate_risk(y, x)

    # metodo per l'aggiornamento dell'osservazione
    def update_obs(self):
        self.glyph_obs = self.current_obs.__getitem__("glyphs")
        self.char_obs = self.current_obs.__getitem__("chars")
        self.color_obs = self.current_obs.__getitem__("colors")
        self.message = self.current_obs.__getitem__("message")
        self.parsed_message = self.parse_message()
        self.bl_stats = self.current_obs.__getitem__("blstats")
        self.all_obs = self.current_obs.__getitem__("tty_chars")

        if self.last_risk_update != self.bl_stats[20]:
            self.update_riskmap()
            self.last_risk_update = self.bl_stats[20]

    def debug_crop(self):
        print(self.char_obs[self.a_yx[0] - 2][self.a_yx[1] - 2], " ",
              self.char_obs[self.a_yx[0] - 2][self.a_yx[1] - 1], " ",
              self.char_obs[self.a_yx[0] - 2][self.a_yx[1]], " ",
              self.char_obs[self.a_yx[0] - 2][self.a_yx[1] + 1], " ",
              self.char_obs[self.a_yx[0] - 2][self.a_yx[1] + 2], " ")
        print(self.char_obs[self.a_yx[0] - 2][self.a_yx[1] - 2], " ",
              self.char_obs[self.a_yx[0] - 1][self.a_yx[1] - 1], " ",
              self.char_obs[self.a_yx[0] - 1][self.a_yx[1]], " ",
              self.char_obs[self.a_yx[0] - 1][self.a_yx[1] + 1], " ",
              self.char_obs[self.a_yx[0] - 1][self.a_yx[1] + 2], " ")
        print(self.char_obs[self.a_yx[0]][self.a_yx[1] - 2], " ",
              self.char_obs[self.a_yx[0]][self.a_yx[1] - 1], " ",
              self.char_obs[self.a_yx[0]][self.a_yx[1]], " ",
              self.char_obs[self.a_yx[0]][self.a_yx[1] + 1], " ",
              self.char_obs[self.a_yx[0]][self.a_yx[1] + 2], " ")
        print(self.char_obs[self.a_yx[0] + 1][self.a_yx[1] - 2], " ",
              self.char_obs[self.a_yx[0] + 1][self.a_yx[1] - 1], " ",
              self.char_obs[self.a_yx[0] + 1][self.a_yx[1]], " ",
              self.char_obs[self.a_yx[0] + 1][self.a_yx[1] + 1], " ",
              self.char_obs[self.a_yx[0] + 1][self.a_yx[1] + 2], " ")
        print(self.char_obs[self.a_yx[0] + 2][self.a_yx[1] - 2], " ",
              self.char_obs[self.a_yx[0] + 2][self.a_yx[1] - 1], " ",
              self.char_obs[self.a_yx[0] + 2][self.a_yx[1]], " ",
              self.char_obs[self.a_yx[0] + 2][self.a_yx[1] + 1], " ",
              self.char_obs[self.a_yx[0] + 2][self.a_yx[1] + 2], " ")

        print(self.color_obs[self.a_yx[0] - 2][self.a_yx[1] - 2], " ",
              self.color_obs[self.a_yx[0] - 2][self.a_yx[1] - 1], " ",
              self.color_obs[self.a_yx[0] - 2][self.a_yx[1]], " ",
              self.color_obs[self.a_yx[0] - 2][self.a_yx[1] + 1], " ",
              self.color_obs[self.a_yx[0] - 2][self.a_yx[1] + 2], " ")
        print(self.color_obs[self.a_yx[0] - 2][self.a_yx[1] - 2], " ",
              self.color_obs[self.a_yx[0] - 1][self.a_yx[1] - 1], " ",
              self.color_obs[self.a_yx[0] - 1][self.a_yx[1]], " ",
              self.color_obs[self.a_yx[0] - 1][self.a_yx[1] + 1], " ",
              self.color_obs[self.a_yx[0] - 1][self.a_yx[1] + 2], " ")
        print(self.color_obs[self.a_yx[0]][self.a_yx[1] - 2], " ",
              self.color_obs[self.a_yx[0]][self.a_yx[1] - 1], " ",
              self.color_obs[self.a_yx[0]][self.a_yx[1]], " ",
              self.color_obs[self.a_yx[0]][self.a_yx[1] + 1], " ",
              self.color_obs[self.a_yx[0]][self.a_yx[1] + 2], " ")
        print(self.color_obs[self.a_yx[0] + 1][self.a_yx[1] - 2], " ",
              self.color_obs[self.a_yx[0] + 1][self.a_yx[1] - 1], " ",
              self.color_obs[self.a_yx[0] + 1][self.a_yx[1]], " ",
              self.color_obs[self.a_yx[0] + 1][self.a_yx[1] + 1], " ",
              self.color_obs[self.a_yx[0] + 1][self.a_yx[1] + 2], " ")
        print(self.color_obs[self.a_yx[0] + 2][self.a_yx[1] - 2], " ",
              self.color_obs[self.a_yx[0] + 2][self.a_yx[1] - 1], " ",
              self.color_obs[self.a_yx[0] + 2][self.a_yx[1]], " ",
              self.color_obs[self.a_yx[0] + 2][self.a_yx[1] + 1], " ",
              self.color_obs[self.a_yx[0] + 2][self.a_yx[1] + 2], " ")

        print(self.glyph_obs[self.a_yx[0] - 2][self.a_yx[1] - 2], " ",
              self.glyph_obs[self.a_yx[0] - 2][self.a_yx[1] - 1], " ",
              self.glyph_obs[self.a_yx[0] - 2][self.a_yx[1]], " ",
              self.glyph_obs[self.a_yx[0] - 2][self.a_yx[1] + 1], " ",
              self.glyph_obs[self.a_yx[0] - 2][self.a_yx[1] + 2], " ")
        print(self.glyph_obs[self.a_yx[0] - 2][self.a_yx[1] - 2], " ",
              self.glyph_obs[self.a_yx[0] - 1][self.a_yx[1] - 1], " ",
              self.glyph_obs[self.a_yx[0] - 1][self.a_yx[1]], " ",
              self.glyph_obs[self.a_yx[0] - 1][self.a_yx[1] + 1], " ",
              self.glyph_obs[self.a_yx[0] - 1][self.a_yx[1] + 2], " ")
        print(self.glyph_obs[self.a_yx[0]][self.a_yx[1] - 2], " ",
              self.glyph_obs[self.a_yx[0]][self.a_yx[1] - 1], " ",
              self.glyph_obs[self.a_yx[0]][self.a_yx[1]], " ",
              self.glyph_obs[self.a_yx[0]][self.a_yx[1] + 1], " ",
              self.glyph_obs[self.a_yx[0]][self.a_yx[1] + 2], " ")
        print(self.glyph_obs[self.a_yx[0] + 1][self.a_yx[1] - 2], " ",
              self.glyph_obs[self.a_yx[0] + 1][self.a_yx[1] - 1], " ",
              self.glyph_obs[self.a_yx[0] + 1][self.a_yx[1]], " ",
              self.glyph_obs[self.a_yx[0] + 1][self.a_yx[1] + 1], " ",
              self.glyph_obs[self.a_yx[0] + 1][self.a_yx[1] + 2], " ")
        print(self.glyph_obs[self.a_yx[0] + 2][self.a_yx[1] - 2], " ",
              self.glyph_obs[self.a_yx[0] + 2][self.a_yx[1] - 1], " ",
              self.glyph_obs[self.a_yx[0] + 2][self.a_yx[1]], " ",
              self.glyph_obs[self.a_yx[0] + 2][self.a_yx[1] + 1], " ",
              self.glyph_obs[self.a_yx[0] + 2][self.a_yx[1] + 2], " ")

        print(self.exception)

    def glyph_cooldown(self, glyph):
        if self.recently_ejected:
            self.recently_ejected = False
            return -1
        char = glyph[0]
        color = glyph[1]
        cooldown = self.cooldown
        if char == 64 and color == 15:
            cooldown = -1
        elif char == 43 and color == 3:
            cooldown = 50
        elif char == 45 or char == 124 and color == 3:
            cooldown = 200
        elif char == 62 or char == 36 or char == 60:
            cooldown = 15
        elif char == 37:
            cooldown = 1
        elif [58, 59, 38, 44].__contains__(char) or 65 <= char <= 90 or 97 <= char <= 122:
            cooldown = 5
        return cooldown

    def find(self, condition, args):
        frontier = list()
        looked_mat = [[0 for i in range(self.size_x)] for j in range(self.size_y)]
        current = (self.a_yx[0], self.a_yx[1])
        found = False

        while current is not None and not found:
            looked_mat[current[0]][current[1]] = 1

            if condition(current, args):
                return True, current[0], current[1]

            nbh = self.neighbors_8_dir(current[0], current[1])

            for next in nbh:
                if looked_mat[next[0]][next[1]] == 0 and not frontier.__contains__(next):
                    frontier.append(next)
            if len(frontier) > 0:
                current = frontier.pop(0)
            else:
                current = None

        return False, -1, -1

    def find_far(self, condition):
        frontier = list()
        looked_mat = [[0 for i in range(self.size_x)] for j in range(self.size_y)]
        current = (self.a_yx[0], self.a_yx[1])

        best = None

        while current is not None:
            looked_mat[current[0]][current[1]] = 1

            if condition(current[0], current[1]):
                best = current

            nbh = self.neighbors_8_dir(current[0], current[1])

            for next in nbh:
                if looked_mat[next[0]][next[1]] == 0 and not frontier.__contains__(next):
                    frontier.append(next)
            if len(frontier) > 0:
                current = frontier.pop(0)
            else:
                current = None

        if best is not None:
            return True, best[0], best[1]
        else:
            return False, -1, -1

    def condition_agent_obj(self, tile, args):
        if args.__contains__((self.char_obs[tile[0]][tile[1]], self.color_obs[tile[0]][tile[1]])) and \
                (self.memory[tile[0]][tile[1]] == -1 or
                 abs(self.memory[tile[0]][tile[1]] - self.act_num) > self.glyph_cooldown(
                            (self.char_obs[tile[0]][tile[1]], self.color_obs[tile[0]][tile[1]]))) \
                and (self.agent_id == self.glyph_obs[tile[0]][tile[1]] or self.agent_id == -1):
            return True
        else:
            return False

    # metodo che individua e aggiorna la posizione dell'agente
    def update_agent(self):
        found_agent, self.a_yx[0], self.a_yx[1] = self.find(self.condition_agent_obj, [(64, 15)])
        return found_agent

    def hard_search(self):
        self.search_map = [[0 for _ in range(self.size_x)] for _ in range(self.size_y)]
        self.search_max = self.hard_search_max
        self.hard_search_max -= 1

    # metodo che effettua il reset della memoria dell'agente
    def reset_memory(self):
        self.exception = []
        self.monster_exception = []
        self.search_max = self.default_search_max
        self.hard_search_max = self.default_hard_search_max
        self.memory = [[-1 for _ in range(self.size_x)] for _ in range(self.size_y)]
        self.search_map = [[0 for _ in range(self.size_x)] for _ in range(self.size_y)]

    def unexplored_walkable_around(self, y, x):
        walkable = 0
        unex_walkable = 0
        door_flag = False
        for i in self.neighbors_8_dir(y, x):
            if self.is_doorway(i[0], i[1]):
                door_flag = True
            if self.char_obs[i[0]][i[1]] == 43 or self.char_obs[i[0]][i[1]] == 96:
                return True
            if self.is_a_monster(i[0], i[1]):
                return True
            if self.is_walkable(i[0], i[1]):
                walkable += 1
            if self.is_walkable(i[0], i[1]) and self.is_unexplored(i[0], i[1]):
                unex_walkable += 1

        if door_flag and walkable == 1 and unex_walkable == 0:
            return False
        if door_flag:
            return True
        if walkable >= 3 or unex_walkable >= 1:
            return True

        return False

    # metodo per stabilire se una casella vada o meno considerata inesplorata
    def is_unexplored(self, y, x):
        if self.memory[y][x] == -1 or abs(self.memory[y][x] - self.act_num) >= self.cooldown:
            return True
        else:
            return False

    def is_walkable(self, y, x):

        char = self.char_obs[y][x]
        color = self.color_obs[y][x]

        if char == 64 and (y != self.a_yx[0] or x != self.a_yx[1]):
            return False

        if self.shop_tiles.__contains__((y, x)):
            return False

        if char == 101 and not self.panic:  # spore or eye
            return False
        elif char == 70 and color != 10 and color != 5 and not self.panic and self.bl_stats[10] < 15:  # Molds
            return False
        # elif char == 98 and color == 2 and not self.panic:  # Acid Blob
        #    return False

        if char == 43 and color != 3:
            return True

        if (self.walkable_glyphs.__contains__((char, color)) or self.walkable_glyphs.__contains__(
                (char, -1))) and not self.exception.__contains__((y, x)):
            if char == 64 and (self.glyph_obs[y][x] != self.agent_id or color != 15):
                return False
            return True
        else:
            return False

    def is_a_monster(self, y, x):
        char = self.char_obs[y][x]
        color = self.color_obs[y][x]

        if self.monster_exception.__contains__((y, x)):
            return False
        # if char == 104 and self.bl_stats[12] >= 3:
        # return False
        if char == 64 and color != 15:
            return True
        if [58, 59, 38, 39, 44].__contains__(char) or 65 <= char <= 90 or 97 <= char <= 122:
            if (char == 102 or char == 100) and (
                    color == 7 or color == 15) and self.pet_alive:  # or (find and self.is_unexplored(y, x)):
                return False
            elif char == 117 and color == 3 and self.pet_alive:  # il pony amico non ?? un mostro
                return False
            elif char == 101 and not self.panic:  # spore or eye
                return False
            elif char == 70 and color != 10 and color != 5 and not self.panic and self.bl_stats[10] < 15:  # Molds
                return False
            # elif char == 98 and color == 2 and not self.panic:  # Acid Blob
            #    return False
            else:
                return True
        else:
            return False

    def is_safe(self, y, x):
        if self.risk_map[y][x] > 0:
            return False
        else:
            return True

    def is_unsearched_wallside(self, y, x):

        if y < self.size_y - 1:
            if (self.char_obs[y + 1][x] == 124 or self.char_obs[y + 1][x] == 45) and \
                    self.color_obs[y + 1][x] == 7 and self.search_map[y + 1][x] == 0:
                return True
        if y > 0:
            if (self.char_obs[y - 1][x] == 124 or self.char_obs[y - 1][x] == 45) and \
                    self.color_obs[y - 1][x] == 7 and self.search_map[y - 1][x] == 0:
                return True
        if x < self.size_x - 1:
            if (self.char_obs[y][x + 1] == 124 or self.char_obs[y][x + 1] == 45) and \
                    self.color_obs[y][x + 1] == 7 and self.search_map[y][x + 1] == 0:
                return True
        if x > 0:
            if (self.char_obs[y][x - 1] == 124 or self.char_obs[y][x - 1] == 45) and \
                    self.color_obs[y][x - 1] == 7 and self.search_map[y][x - 1] == 0:
                return True
        return False

    def is_unsearched_voidside(self, y, x):

        if y < self.size_y - 1:
            if self.char_obs[y + 1][x] == 32 and self.search_map[y + 1][x] == 0:
                return True
        if y > 0:
            if self.char_obs[y - 1][x] == 32 and self.search_map[y - 1][x] == 0:
                return True
        if x < self.size_x - 1:
            if self.char_obs[y][x + 1] == 32 and self.search_map[y][x + 1] == 0:
                return True
        if x > 0:
            if self.char_obs[y][x - 1] == 32 and self.search_map[y][x - 1] == 0:
                return True
        return False

    def is_doorway(self, y, x):
        char = self.char_obs[y][x]
        color = self.color_obs[y][x]
        if (
                char == 43 or char == 124 or char == 45) and color == 3:  # or (char == 46 and self.is_unexplored(y, x)): wip
            return True
        walls_count_h = 0
        walls_count_v = 0
        if y < self.size_y - 1:
            if (self.char_obs[y + 1][x] == 124 or self.char_obs[y + 1][x] == 45) and \
                    self.color_obs[y + 1][x] == 7:
                walls_count_v += 1
        if y > 0:
            if (self.char_obs[y - 1][x] == 124 or self.char_obs[y - 1][x] == 45) and \
                    self.color_obs[y - 1][x] == 7:
                walls_count_v += 1
        if x < self.size_x - 1:
            if (self.char_obs[y][x + 1] == 124 or self.char_obs[y][x + 1] == 45) and \
                    self.color_obs[y][x + 1] == 7:
                walls_count_h += 1
        if x > 0:
            if (self.char_obs[y][x - 1] == 124 or self.char_obs[y][x - 1] == 45) and \
                    self.color_obs[y][x - 1] == 7:
                walls_count_h += 1

        if walls_count_h == 2 or walls_count_v == 2:
            return True
        else:
            return False

    def is_isolated(self, y, x, glyph, cross):
        same_glyph_count = 0
        near = self.neighbors_8_dir(y, x)
        while len(near) > 0:
            next = near.pop()
            if cross and next[0] != y and next[1] != x:
                continue
            if glyph is None:
                if self.glyph_obs[next[0]][next[1]] == self.glyph_obs[y][x] or self.is_doorway(next[0], next[1]):
                    same_glyph_count += 1
            else:
                char = glyph[0]
                color = glyph[1]
                if (self.char_obs[next[0]][next[1]] == char and self.color_obs[next[0]][
                    next[1]] == color) or self.is_doorway(next[0], next[1]):
                    same_glyph_count += 1
        if same_glyph_count < 2:
            return True
        else:
            return False

    def is_near_glyph(self, y, x, glyph, dir_num):
        char = glyph[0]
        color = glyph[1]
        around_it = []
        if dir_num == 8:
            around_it = self.neighbors_8_dir(y, x)
        if dir_num == 4:
            around_it = self.neighbors_4_dir(y, x)
        while len(around_it) > 0:
            near = around_it.pop()
            if self.char_obs[near[0]][near[1]] == char and (self.color_obs[near[0]][near[1]] == color or color == -1):
                return True
        return False

    def neighbors_8_dir(self, y, x):
        neighborhood = self.neighbors_4_dir(y, x)

        if y > 0:
            if x > 0:
                neighborhood.append((y - 1, x - 1))  # nw
            if x < self.size_x - 1:
                neighborhood.append((y - 1, x + 1))  # ne
        if x < self.size_x - 1:
            if y < self.size_y - 1:
                neighborhood.append((y + 1, x + 1))  # se
        if y < self.size_y - 1:
            if x > 0:
                neighborhood.append((y + 1, x - 1))  # sw

        return neighborhood

    def neighbors_4_dir(self, y, x):
        neighborhood = list()
        if y > 0:
            neighborhood.append((y - 1, x))  # n
        if x < self.size_x - 1:
            neighborhood.append((y, x + 1))  # e
        if y < self.size_y - 1:
            neighborhood.append((y + 1, x))  # s
        if x > 0:
            neighborhood.append((y, x - 1))  # w
        return neighborhood

    def neighbors(self, y, x, safe):
        neighborhood = list()
        doorway = self.is_doorway(y, x)
        if y > 0:
            if self.is_walkable(y - 1, x) and (not safe or self.is_safe(y - 1, x)):
                neighborhood.append((y - 1, x))  # n
            if x > 0:
                if self.is_walkable(y - 1, x - 1) and (not safe or self.is_safe(y - 1, x - 1)) and not doorway:
                    if not self.is_doorway(y - 1, x - 1):
                        neighborhood.append((y - 1, x - 1))  # nw
            if x < self.size_x - 1:
                if self.is_walkable(y - 1, x + 1) and (not safe or self.is_safe(y - 1, x + 1)) and not doorway:
                    if not self.is_doorway(y - 1, x + 1):
                        neighborhood.append((y - 1, x + 1))  # ne
        if x < self.size_x - 1:
            if self.is_walkable(y, x + 1) and (not safe or self.is_safe(y, x + 1)):
                neighborhood.append((y, x + 1))  # e
            if y < self.size_y - 1:
                if self.is_walkable(y + 1, x + 1) and (not safe or self.is_safe(y + 1, x + 1)) and not doorway:
                    if not self.is_doorway(y + 1, x + 1):
                        neighborhood.append((y + 1, x + 1))  # se
        if y < self.size_y - 1:
            if self.is_walkable(y + 1, x) and (not safe or self.is_safe(y + 1, x)):
                neighborhood.append((y + 1, x))  # s
            if x > 0:
                if self.is_walkable(y + 1, x - 1) and (not safe or self.is_safe(y + 1, x - 1)) and not doorway:
                    if not self.is_doorway(y + 1, x - 1):
                        neighborhood.append((y + 1, x - 1))  # sw
        if x > 0:
            if self.is_walkable(y, x - 1) and (not safe or self.is_safe(y, x - 1)):
                neighborhood.append((y, x - 1))  # w
        return neighborhood

    def parse_message(self):
        parsed_string = ""
        for c in self.message:
            parsed_string = parsed_string + chr(c)
        return parsed_string

    def parse_all(self):
        parsed_string = ""
        for i in range(0, 24):
            for j in range(0, 80):
                c = self.all_obs[i][j]
                parsed_string = parsed_string + chr(c)
        return parsed_string

    def do_it(self, x, direction):
        #print(self.bl_stats)
        self.old_turn = self.bl_stats[20]
        rew = 0
        done = False
        info = None

        if not self.fast_mode:
            print("pray_timeout: ", abs(self.last_pray - self.bl_stats[20]))
        if self.bl_stats[20] % 100 == 0:
            print("guard_encounter: ", self.guard_encounter, " avanzamento - score: ", self.bl_stats[9], " turno: ",
                  self.bl_stats[20], " ora: ", time.localtime()[3], "-", time.localtime()[4], "pray_timeout: ",
                  abs(self.last_pray - self.bl_stats[20]), " -----")
            go_back(2)

        if abs(self.bl_stats[20] - self.pet_alive_turn) > 10 and self.bl_stats[20] > 3000:
            self.pet_alive = False

        if self.act_num % 50 == 0:  # modifica
            self.panic = False

        if self.ran:
            if abs(self.ran_turn - self.bl_stats[20]) > self.ran_cooldown:
                self.ran = False

        if self.parsed_message.__contains__("Closed for inventory"):
            for tile in self.neighbors_4_dir(self.a_yx[0], self.a_yx[1]):
                if self.char_obs[tile[0]][tile[1]] == 43 and self.color_obs[tile[0]][tile[1]] == 3:
                    self.shop_tiles.append(tile)

        if self.update_agent():
            self.current_obs, rew, done, info = env.step(38)

            if self.parsed_message.__contains__("Closed for inventory"):
                for tile in self.neighbors_4_dir(self.a_yx[0], self.a_yx[1]):
                    if self.char_obs[tile[0]][tile[1]] == 43 and self.color_obs[tile[0]][tile[1]] == 3:
                        self.shop_tiles.append(tile)

        if self.score < self.bl_stats[9]:
            self.score = self.bl_stats[9]

        if self.parsed_message.__contains__("Hello stranger, who are you?"):  # respond Croesus
            self.guard_encounter += 1
            return -1, True, None

        if self.update_agent():
            self.current_obs, rew, done, info = env.step(38)

        if self.update_agent():
            self.current_obs, rew, done, info = env.step(x)
        self.update_obs()

        if self.parsed_message.__contains__("swap"):
            self.pet_alive = True
            self.pet_alive_turn = self.bl_stats[20]
        if direction is not None and self.parsed_message.__contains__("In what direction?"):
            self.current_obs, rew, done, info = env.step(direction)
            self.update_obs()

        if self.parsed_message.__contains__("Are you sure you want to pray?") or self.parsed_message.__contains__(
                "Really attack"):
            self.current_obs, rew, done, info = env.step(7)  # yes
            self.update_obs()
        if self.parsed_message.__contains__("You are carrying too much to get through."):
            next = self.inverse_move_translator(self.a_yx[0], self.a_yx[1], x)
            self.exception.append(next)
            self.update_obs()
        if self.parsed_message.__contains__("What do you want to write with?"):
            self.current_obs, rew, done, info = env.step(106)  # -
            self.update_obs()
        if self.parsed_message.__contains__("You write in the dust with your fingertip."):
            self.current_obs, rew, done, info = env.step(19)  # more
            self.update_obs()
        if self.parsed_message.__contains__("What do you want to write in the dust here?"):
            self.current_obs, rew, done, info = env.step(36)  # E
            self.current_obs, rew, done, info = env.step(1)  # l
            self.current_obs, rew, done, info = env.step(6)  # b
            self.current_obs, rew, done, info = env.step(35)  # e
            self.current_obs, rew, done, info = env.step(67)  # r
            self.current_obs, rew, done, info = env.step(35)  # e
            self.current_obs, rew, done, info = env.step(91)  # t
            self.current_obs, rew, done, info = env.step(3)  # h
            self.current_obs, rew, done, info = env.step(19)  # more
            self.update_obs()

        if self.parsed_message.__contains__("You swap places"):
            self.pet_alive = True

        if self.parsed_message.__contains__("Closed for inventory"):
            for tile in self.neighbors_4_dir(self.a_yx[0], self.a_yx[1]):
                if self.char_obs[tile[0]][tile[1]] == 43 and self.color_obs[tile[0]][tile[1]] == 3:
                    self.shop_tiles.append(tile)

        if ((self.parsed_message.__contains__("Welcome") and self.parsed_message.__contains__(
                "\"")) or self.parsed_message.__contains__("\"How dare you break my door?\"")) and not 0 <= \
                                                                                                       self.bl_stats[
                                                                                                           20] <= 5:
            self.shop_propagation(self.a_yx)

        if self.bl_stats[11] != 0 and (self.bl_stats[10] / self.bl_stats[11]) <= 0.5 and not self.safe_play:
            if not self.fast_mode:
                print("SAFE_MODE : enabled")
            self.safe_play = True
        elif self.bl_stats[11] != 0 and (self.bl_stats[10] / self.bl_stats[11]) > 0.85 and self.safe_play:
            if not self.fast_mode:
                print("SAFE_MODE : disabled")
            self.safe_play = False
        self.act_num += 1
        if self.update_agent():
            self.memory[self.a_yx[0]][self.a_yx[1]] = self.act_num
            if x == 75:  # it was a search
                self.search_map[self.a_yx[0]][self.a_yx[1]] = 1
                for next in self.neighbors_8_dir(self.a_yx[0], self.a_yx[1]):
                    self.search_map[next[0]][next[1]] = 1
        if not self.fast_mode:  # and x != 10:
            #go_back(27)
            env.render()
            time.sleep(0)
        self.new_turn = self.bl_stats[20]
        return rew, done, info

    def shop_propagation(self, tile):
        for near in self.neighbors_8_dir(tile[0], tile[1]):
            char = self.char_obs[near[0]][near[1]]
            if char == 124 or char == 45 or char == 35 or char == 32 or (
                    near[0] == self.a_yx[0] and near[1] == self.a_yx[
                1]):  # or ([58,59,38,39,44].__contains__(char) or 65 <= char <= 90 or 97 <= char <= 122) :
                continue
            elif not self.shop_tiles.__contains__(near):
                self.shop_tiles.append(near)
                self.shop_propagation(near)

    @staticmethod
    def move_translator(from_y, from_x, to_y, to_x):
        if to_y > from_y:  # la y del next ?? maggiore -> movimenti verso sud
            if to_x > from_x:
                move = 5  # se
            elif to_x == from_x:
                move = 2  # s
            else:
                move = 6  # sw

        elif to_y == from_y:  # la y del next ?? uguale -> movimenti verso est ed ovest
            if to_x > from_x:
                move = 1  # e
            else:
                move = 3  # w
        else:  # la y del next ?? minore -> movimenti verso nord
            if to_x > from_x:
                move = 4  # ne
            elif to_x == from_x:
                move = 0  # n
            else:
                move = 7  # nw

        return move

    @staticmethod
    def inverse_move_translator(from_y, from_x, dir):
        if dir == 0:
            return from_y - 1, from_x
        elif dir == 4:
            return from_y - 1, from_x + 1
        elif dir == 1:
            return from_y, from_x + 1
        elif dir == 5:
            return from_y + 1, from_x + 1
        elif dir == 2:
            return from_y + 1, from_x
        elif dir == 6:
            return from_y + 1, from_x - 1
        elif dir == 3:
            return from_y, from_x - 1
        elif dir == 7:
            return from_y - 1, from_x - 1

    def reset_game(self):
        self.current_obs = env.reset()
        self.new_turn = 0
        self.old_turn = 0
        self.update_obs()
        self.reset_memory()
        self.safe_play = False
        self.agent_id = -1
        self.update_agent()
        self.agent_id = self.glyph_obs[self.a_yx[0]][self.a_yx[1]]
        self.memory[self.a_yx[0]][self.a_yx[1]] = self.act_num
        if not self.fast_mode:
            env.render()
        self.engraved_tiles = []
        self.inedible = []
        self.shop_tiles = []
        self.u_stairs_locations = []
        self.d_stairs_locations = []
        self.total_score += self.score
        self.score = 0
        self.recently_killed = []
        self.last_pray = -1

    def partial_reset_game(self):
        self.pet_alive = False
        self.update_obs()
        self.reset_memory()
        self.engraved_tiles = []
        self.recently_killed = []
        self.shop_tiles = []
        self.inedible = []

    def check_exception(self, tile):
        return self.exception.__contains__((tile[0], tile[1]))

    def append_exception(self, tile):
        self.exception.append(tile)

    def check_engraved(self, tile):
        return self.engraved_tiles.__contains__((tile[0], tile[1]))

    def append_engraved(self, tile):
        self.engraved_tiles.append(tile)

    def check_monster_exception(self, tile):
        return self.monster_exception.__contains__((tile[0], tile[1]))

    def append_monster_exception(self, tile):
        self.monster_exception.append(tile)

    def check_inedible(self, tile):
        return self.inedible.__contains__((tile[0], tile[1]))

    def append_inedible(self, tile):
        self.inedible.append(tile)

    def reset_inedible(self):
        self.inedible = []

    def get_recently_killed(self):
        return self.recently_killed

    def append_recently_killed(self, data):
        self.exception.append(data)

    def check_recently_ejected(self):
        return self.recently_ejected

    def notify_recently_ejected(self):
        self.recently_ejected = True

    def update_memory(self, y, x):
        self.memory[y][x] = self.act_num

    def clear_memory(self, y, x):
        self.memory[y][x] = -1

    def update_last_monster_searched(self, char, color, times):
        self.last_monster_searched = (char, color, times)

    def get_last_monster_searched(self):
        return self.last_monster_searched

    def get_agent_position(self):
        return self.a_yx

    def get_size_x(self):
        return self.size_x

    def get_size_y(self):
        return self.size_y

    def get_act_num(self):
        return self.act_num

    def get_memory(self, y, x):
        return self.memory[y][x]

    def get_risk(self, y, x):
        return self.risk_map[y][x]

    def force_risk(self, y, x, risk):
        self.risk_map[y][x] = risk

    def get_glyph(self, y, x):
        return self.glyph_obs[y][x]

    def get_char(self, y, x):
        return self.char_obs[y][x]

    def get_color(self, y, x):
        return self.color_obs[y][x]

    def get_parsed_message(self):
        return self.parsed_message

    def get_bl_stats(self):
        return self.bl_stats

    def get_safe_play(self):
        return self.safe_play

    def get_pet_alive(self):
        return self.pet_alive

    def get_actual_score(self):
        return self.score

    def get_total_score(self):
        return self.total_score

    def get_stairs_locations(self):
        return self.u_stairs_locations, self.d_stairs_locations

    def append_stairs_location(self, stairs, u):
        if u:
            self.u_stairs_locations.append(stairs)
        else:
            self.d_stairs_locations.append(stairs)

    def get_last_pray(self):
        return self.last_pray

    def update_last_pray(self):
        self.last_pray = self.bl_stats[20]

    def update_ran(self):
        self.ran = True
        self.ran_turn = self.bl_stats[20]

    def reset_ran(self):
        self.ran = False

    def get_ran(self):
        return self.ran

    def get_new_turn(self):
        return self.new_turn

    def get_old_turn(self):
        return self.old_turn

    def get_search_max(self):
        return self.search_max

    def stuck(self):
        self.stuck_counter += 1

    def reset_stuck_counter(self):
        self.stuck_counter = 0

    def get_stuck_counter(self):
        return self.stuck_counter

    def increment_hard_search_num(self):
        self.hard_search_num += 1

    def reset_hard_search_num(self):
        self.hard_search_num = 0

    def get_hard_search_num(self):
        return self.hard_search_num

    def get_fast_mode(self):
        return self.fast_mode


class DungeonWalker:

    def __init__(self, game):
        self.game = game

    # euristica per il calcolo della distanza tra due caselle della griglia 8-direzionale
    def h_octile_distance(self, ay, ax, oy, ox):
        x_d = abs(ax - ox)
        y_d = abs(ay - oy)
        return (1.414 * min(x_d, y_d)) + abs(x_d - y_d)

    def a_star(self, oy, ox, safe):
        # voglio che restituisca il cammino
        # lista di priorit?? rappresentante la frontiera
        frontier = PriorityQueue()
        agent = self.game.get_agent_position()
        # inizializzo l'algoritmo inserendo nella lista il nodo iniziale (posizione agente) (priorit?? massima ->0)
        frontier.put(((agent[0], agent[1]), 0))
        # dizionario in cui associo ai nodi il predecessore
        came_from: Dict[Location, Optional[Location]] = {}
        # dizionario in cui associo ai nodi il costo f(n) accumalatovi
        cost_so_far: Dict[Location, float] = {}
        came_from[(agent[0], agent[1])] = None
        cost_so_far[(agent[0], agent[1])] = 0

        while not frontier.empty():
            current = frontier.get()

            if current == (oy, ox):  # abbiamo raggiunto il goal
                break
            near = self.game.neighbors(current[0][0], current[0][1], safe)
            for next in near:  # per cella adiacente alla corrente
                new_cost = cost_so_far[current[0]] + 1
                if next not in cost_so_far or new_cost < cost_so_far[next]:
                    cost_so_far[next] = new_cost
                    priority = new_cost + self.h_octile_distance(next[0], next[1], oy, ox)
                    frontier.put((next, priority))
                    came_from[next] = current[0]
        return came_from, cost_so_far

    def path_finder(self, oy, ox, not_reach_diag, safe_play):

        yellow_brick_road = list()

        agent = self.game.get_agent_position()
        if self.game.get_risk(agent[0], agent[1]) >= 2 and safe_play:
            return yellow_brick_road

        came_from, cost_so_far = self.a_star(oy, ox, safe_play)
        cursor = (oy, ox)
        next = None
        while cursor is not None:
            if next is not None:

                if not_reach_diag and next[0] == oy and next[1] == ox and next[0] != cursor[0] and next[1] != cursor[1]:
                    # il prossimo nodo ?? l'obbiettivo e non deve essere raggiunto in diagonale
                    if next[0] > cursor[0] and next[1] > cursor[1]:  # y e x maggiori -> se
                        if self.game.is_walkable(cursor[0], cursor[1] + 1):
                            yellow_brick_road.append(2)  # s
                            yellow_brick_road.append(1)  # e
                        elif self.game.is_walkable(cursor[0] + 1, cursor[1]):
                            yellow_brick_road.append(1)  # e
                            yellow_brick_road.append(2)  # s
                    elif next[0] > cursor[0] and next[1] < cursor[1]:  # y maggiore e x minore -> sw
                        if self.game.is_walkable(cursor[0], cursor[1] - 1):
                            yellow_brick_road.append(2)  # s
                            yellow_brick_road.append(3)  # w
                        elif self.game.is_walkable(cursor[0] + 1, cursor[1]):
                            yellow_brick_road.append(3)  # w
                            yellow_brick_road.append(2)  # s
                    elif next[0] < cursor[0] and next[1] < cursor[1]:  # y minore e x maggiore -> nw
                        if self.game.is_walkable(cursor[0], cursor[1] - 1):
                            yellow_brick_road.append(0)  # n
                            yellow_brick_road.append(3)  # w
                        elif self.game.is_walkable(cursor[0] - 1, cursor[1]):
                            yellow_brick_road.append(3)  # w
                            yellow_brick_road.append(0)  # n
                    elif next[0] < cursor[0] and next[1] > cursor[1]:  # y minore e x minore -> ne
                        if self.game.is_walkable(cursor[0], cursor[1] + 1):
                            yellow_brick_road.append(0)  # n
                            yellow_brick_road.append(1)  # e
                        elif self.game.is_walkable(cursor[0] - 1, cursor[1]):
                            yellow_brick_road.append(1)  # e
                            yellow_brick_road.append(0)  # n

                yellow_brick_road.append(self.game.move_translator(cursor[0], cursor[1], next[0], next[1]))
            next = cursor
            try:
                cursor = came_from[cursor]
            except:
                return None

        return yellow_brick_road


# archetipo per ogni possibile tipo di task
class Task:
    def __init__(self, dungeon_walker, game, task_name):
        self.dungeon_walker = dungeon_walker
        self.game = game
        self.name = task_name

    # condizione per interrompere con emergenza ci?? che si sta facendo
    def eject_button(self):
        if self.game.update_agent():
            self.game.update_obs()
            agent = self.game.get_agent_position()

            if self.game.get_risk(agent[0], agent[1]) > 1:
                self.game.notify_recently_ejected()
                return True
        return False

    @staticmethod
    def custom_contain(list, value):
        for item in list:
            if item[0] == value:
                return True, (item[1], item[2])
        return False, (-1, -1)

    def surely_not_a_trap(self, y, x):
        for log in self.game.get_recently_killed():
            if log[2] == y and log[3] == x:
                return True
        return False

    # metodo per l'esecuzione di piani articolati
    def do_plan(self, plan):
        size = len(plan)
        done = False
        info = None
        rew = 0
        i = 0
        while 0 <= i < size and not done:
            action = plan.pop()
            agent = self.game.get_agent_position()
            next_tile = self.game.inverse_move_translator(agent[0], agent[1], action)
            if self.game.update_agent():
                if self.game.get_char(next_tile[0], next_tile[1]) == 37 and not self.surely_not_a_trap(next_tile[0],
                                                                                                       next_tile[
                                                                                                           1]):  # se la prossima casella contiene del cibo
                    for k in range(0, 10):
                        rew, done, info = self.game.do_it(96, action)  # untrap
                if self.game.is_walkable(next_tile[0], next_tile[1]):
                    rew, done, info = self.game.do_it(action, None)
                else:
                    return -1, False, None  # failure
            else:
                rew = 0
                done = True
                break
            message = self.game.get_parsed_message()
            if message.__contains__("It's solid stone.") or \
                    message.__contains__("It's a wall.") or \
                    message.__contains__("You can't move diagonally into an intact doorway.") or \
                    message.__contains__("You try to move the boulder, but in vain.") or \
                    message.__contains__("Perhaps that's why you cannot move it.") or \
                    message.__contains__("You hear a monster behind the boulder."):
                self.game.append_exception(next_tile)
                return -1, False, None  # failure
            if self.eject_button():
                return -1, False, None
            i += 1
        return rew, done, info

    def standard_condition(self, tile, args):
        if (args.__contains__((self.game.get_char(tile[0], tile[1]), self.game.get_color(tile[0], tile[1]))) or
            ((self.game.get_char(tile[0], tile[1]) == 36 or
              (self.game.get_char(tile[0], tile[1]) == 37 and not self.game.check_inedible(
                  tile))) and args.__contains__((self.game.get_char(tile[0], tile[1]), -1)))) and \
                not (self.game.check_exception(tile) and self.game.get_char(tile[0], tile[1]) == 43) and \
                (self.game.get_memory(tile[0], tile[1]) == -1 or
                 abs(self.game.get_memory(tile[0], tile[1]) - self.game.get_act_num()) > self.game.glyph_cooldown(
                            (self.game.get_char(tile[0], tile[1]), self.game.get_color(tile[0], tile[1])))):
            return True
        else:
            return False

    # metodo ausiliario per la ricerca e il pathfinding verso un gruppo di obbiettivi generici
    def standard_plan(self, glyphs, not_reach_diag, safe_play):
        found, y, x = self.game.find(self.standard_condition, glyphs)
        if found:
            char = self.game.get_char(y, x)
            stats = self.game.get_bl_stats()
            if char == 60 and not self.custom_contain(self.game.get_stairs_locations()[0], stats[12])[0]:
                self.game.append_stairs_location((stats[12], y, x), True)

            if char == 62 and not self.custom_contain(self.game.get_stairs_locations()[1], stats[12])[0]:
                self.game.append_stairs_location((stats[12], y, x), False)

            path = self.dungeon_walker.path_finder(y, x, not_reach_diag, safe_play)
            self.game.update_memory(y, x)
            return path, (y, x)
        return None, (-1, -1)

    def planning(self, stats, safe_play, agent):
        return self.name, None, None

    def execution(self, path, arg1, agent, stats):
        return 0, False, None

    def get_name(self):
        return self.name


# archetipo per task che prevedono il raggiungimento di un obbiettivo
class ReachTask(Task):
    def __init__(self, dungeon_walker, game, task_name):
        super().__init__(dungeon_walker, game, task_name)

    def execution(self, path, arg1, agent, stats):
        rew, done, info = self.do_plan(path)
        if rew == -1:
            game.clear_memory(arg1[0], arg1[1])
        return rew, done, info


# archetipo per task che prevedono la ricerca di percorsi nascosti
class HiddenTask(Task):
    def __init__(self, dungeon_walker, game, task_name):
        super().__init__(dungeon_walker, game, task_name)

    def condition_unsearched_obj(self, tile, args):
        glyph = args[0]
        char = glyph[0]
        color = glyph[1]
        if self.game.get_char(tile[0], tile[1]) == char and self.game.get_color(tile[0], tile[1]) == color:
            if char == 46:
                if self.game.is_unsearched_wallside(tile[0], tile[1]):
                    return True
            elif char == 35 and color == 7:
                if self.game.is_unsearched_voidside(tile[0], tile[1]):
                    return True
        return False

    # metodo ausiliario per la ricerca e il pathfinding verso un obbiettivo in cui non ?? mai stata effettuata una search
    def unsearched_plan(self, glyph, safe_play):
        found, y, x = self.game.find(self.condition_unsearched_obj, glyph)
        if found:
            path = self.dungeon_walker.path_finder(y, x, False, safe_play)
            self.game.update_memory(y, x)
            return path, (y, x)
        return None, (-1, -1)

    def execution(self, path, arg1, agent, stats): # in search room corridor
        rew, done, info = self.do_plan(path)
        if rew == -1:
            game.clear_memory(arg1[0], arg1[1])
            return rew, done, info
        if not done and rew != -1:
            j = 0
            while j < game.get_search_max() and not done and not game.get_parsed_message().__contains__(
                    "You find") and not self.eject_button():
                if not game.get_fast_mode():
                    print(self.name, " try: ", j)

                if 3 <= stats[21] <= 4:
                    break

                rew, done, info = game.do_it(75, None)  # search
                stats = game.get_bl_stats()
                j += 1
        return rew, done, info


class StairsDescent(Task):
    def __init__(self, dungeon_walker, game, task_name):
        super().__init__(dungeon_walker, game, task_name)

    def planning(self, stats, safe_play, agent):
        if not self.custom_contain(game.get_stairs_locations()[0], stats[12])[0]:
            found, y, x = game.find(self.standard_condition, [60])
            if found:
                game.get_stairs_locations()[0].append((stats[12], y, x))

        if not self.custom_contain(game.get_stairs_locations()[1], stats[12])[0]:
            found, y, x = game.find(self.standard_condition, [62])
            if found:
                game.get_stairs_locations()[1].append((stats[12], y, x))

        if not 2 <= stats[21] <= 4 or stats[18] + 1 <= stats[
            12]:  # and not self.bl_stats[18] >= self.bl_stats[12] + 3: v2.0
            return None, None, None

        known, coords = self.custom_contain(game.get_stairs_locations()[1], stats[12])

        if not known:
            path, coords = self.standard_plan([(62, 7)], False, False)
        else:
            path = self.dungeon_walker.path_finder(coords[0], coords[1], False, False)
            game.update_memory(coords[0], coords[1])
        if path is None:
            return None, None, None
        else:
            return self.name, path, coords

    def execution(self, path, arg1, agent, stats):
        rew, done, info = self.do_plan(path)
        if rew == -1:
            game.clear_memory(arg1[0], arg1[1])
            return rew, done, info
        agent = game.get_agent_position()
        if not done and agent[0] == arg1[0] and agent[1] == arg1[1]:
            rew, done, info = game.do_it(17, None)  # go down
            agent = game.get_agent_position()
            game.partial_reset_game()
            game.reset_hard_search_num()  # ricorda
            if game.update_agent():
                game.update_memory(agent[0], agent[1])
        return rew, done, info


class StairsAscent(Task):
    def __init__(self, dungeon_walker, game, task_name):
        super().__init__(dungeon_walker, game, task_name)

    def planning(self, stats, safe_play, agent):
        if stats[12] == 1 or 2 <= stats[21] <= 4 or stats[18] >= stats[
            12] + 2:  # or self.bl_stats[18] >= self.bl_stats[12] + 3:
            return None, None, None
        known, coords = self.custom_contain(game.get_stairs_locations()[0], stats[12])
        if not known:
            path, coords = self.standard_plan([(60, 7)], False, False)
        else:
            path = self.dungeon_walker.path_finder(coords[0], coords[1], False, False)
            game.update_memory(coords[0], coords[1])
        if path is None:
            return None, None, None
        else:
            return self.name, path, coords

    def execution(self, path, arg1, agent, stats):
        rew, done, info = self.do_plan(path)
        if rew == -1:
            game.clear_memory(arg1[0], arg1[1])
            return rew, done, info
        agent = game.get_agent_position()
        if not done and agent[0] == arg1[0] and agent[1] == arg1[1]:
            rew, done, info = game.do_it(16, None)  # go up
            agent = game.get_agent_position()
            game.partial_reset_game()
            game.reset_hard_search_num()  # ricorda
            if game.update_agent():
                game.update_memory(agent[0], agent[1])
        return rew, done, info


class Pray(Task):
    def __init__(self, dungeon_walker, game, task_name):
        super().__init__(dungeon_walker, game, task_name)

    def planning(self, stats, safe_play, agent):
        if (3 <= stats[21] <= 4 or stats[10] <= 6 or (
                stats[11] != 0 and (stats[10] / stats[11]) < 0.14)) and (
                abs(game.get_last_pray() - stats[20]) >= 800 or game.get_last_pray() == -1) and stats[
                20] > 300:
            return self.name, None, None

    def execution(self, path, arg1, agent, stats):
        if game.update_agent():
            rew, done, info = game.do_it(62, None)  # pray
            game.update_last_pray()
        else:
            rew = 0
            done = True
            info = None
        return rew, done, info


class Elbereth(Task):
    def __init__(self, dungeon_walker, game, task_name):
        super().__init__(dungeon_walker, game, task_name)

    def planning(self, stats, safe_play, agent):
        for tile in game.neighbors_8_dir(agent[0], agent[1]):
            char = game.get_char(tile[0], tile[1])
            color = game.get_color(tile[0], tile[1])
            if (char == 66 and color == 1) or \
                    (char == 104 and (color == 1 or color == 3)) or \
                    (char == 64 and (color == 1 or color == 3)):
                continue

        if not game.check_engraved(agent) and (
                game.get_risk(agent[0], agent[1]) > 4 or (stats[11] != 0 and (stats[10] / stats[11]) <= 0.7)):
            return self.name, None, None

    def execution(self, path, arg1, agent, stats):
        rew, done, info = game.do_it(36, None)  # engrave
        game.append_engraved((agent[0], agent[1]))

        if not game.get_parsed_message().__contains__("flee"):
            return rew, done, info

        w_count = 0
        risk = game.get_risk(agent[0], agent[1])
        while ((stats[11] != 0 and (stats[10] / stats[11]) < 0.8) or
               risk > 2) and not done and not (w_count > 1 and risk >= 2):
            rew, done, info = game.do_it(75, None)  # wait - with search
            risk = game.get_risk(agent[0], agent[1])
            w_count += 1
        return rew, done, info


class Run(Task):
    def __init__(self, dungeon_walker, game, task_name):
        super().__init__(dungeon_walker, game, task_name)

    def planning(self, stats, safe_play, agent):
        for tile in game.neighbors_8_dir(agent[0], agent[1]):
            char = game.get_char(tile[0], tile[1])
            color = game.get_color(tile[0], tile[1])
            if (char == 100 and color == 1) or \
                    (char == 117 and not game.get_pet_alive()) or \
                    ((char == 102 or char == 100) and (
                            color == 7 or color == 15) and not game.get_pet_alive()) or \
                    (char == 64 and (color == 1 or color == 3)) or \
                    (char == 97) or \
                    (char == 66):
                continue
        risk = game.get_risk(agent[0], agent[1])
        if risk < 1 or risk > 3 or (
                stats[11] != 0 and (stats[10] / stats[11]) > 0.50) or game.get_ran():
            return None, None, None
        else:
            if game.is_doorway(agent[0], agent[1]):
                around_me = game.neighbors_4_dir(agent[0], agent[1])
            else:
                around_me = game.neighbors_8_dir(agent[0], agent[1])
            champion = agent
            found = False
            for tile in around_me:
                risk_c = game.get_risk(champion[0], champion[1])
                risk_t = game.get_risk(tile[0], tile[1])
                char = game.get_char(tile[0], tile[1])
                if risk_c > risk_t and game.is_walkable(tile[0], tile[1]) and \
                        char != 100 and \
                        char != 102 and \
                        char != 117 and \
                        char != 96:

                    if not (game.is_doorway(tile[0], tile[1]) and agent[0] != tile[0] and agent[1] !=
                            tile[1]):
                        if abs(game.get_memory(tile[0], tile[1]) - game.get_act_num()) > 2:
                            champion = tile
                            found = True
            if found:
                return self.name, None, champion
            else:
                return None, None, None

    def execution(self, path, arg1, agent, stats):
        rew, done, info = game.do_it(
            game.move_translator(agent[0], agent[1], arg1[0], arg1[1]),
            None)
        message = game.get_parsed_message()
        if (message.__contains__("fox") or
            message.__contains__("dog") or
            message.__contains__("pony") or
            message.__contains__("kitten") or
            message.__contains__("ant") or
            message.__contains__("throw") or
            message.__contains__("bat") or
            message.__contains__("bee")) and \
                not message.__contains__("swap"):
            game.update_ran()
        else:
            game.reset_ran()
        return rew, done, info


class ExploreClosest(Task):
    def __init__(self, dungeon_walker, game, task_name):
        self.chosen_task = None
        super().__init__(dungeon_walker, game, task_name)

    # metodo ausiliario per la ricerca e il pathfinding verso la casella adiacente ad un gruppo di obbiettivi
    def mixed_plan(self, glyphs, condition, safe_play):
        path = None
        found, y, x = self.game.find(condition, glyphs)
        if found:
            char = self.game.get_char(y, x)
            color = self.game.get_color(y, x)
            if char == 43 and color == 3:
                ny = -1
                nx = -1
                near = self.game.neighbors_4_dir(y, x)
                while len(near) > 0:
                    next = near.pop()
                    if self.game.is_walkable(next[0], next[1]):
                        ny = next[0]
                        nx = next[1]
                        break
                path = self.dungeon_walker.path_finder(ny, nx, False, safe_play)
            elif char == 35:
                path = self.dungeon_walker.path_finder(y, x, False, safe_play)
            else:
                path = self.dungeon_walker.path_finder(y, x, True, safe_play)
        self.game.update_memory(y, x)
        return path, (y, x)

    def condition_multiple_obj_v0(self, tile, args):

        if args.__contains__((self.game.get_char(tile[0], tile[1]), self.game.get_color(tile[0], tile[1]))) and \
                (self.game.get_memory(tile[0], tile[1]) == -1 or
                 (not self.game.get_char(tile[0], tile[1]) == 35 and abs(
                     self.game.get_memory(tile[0], tile[1]) - self.game.get_act_num()) >
                  self.game.glyph_cooldown(
                      (self.game.get_char(tile[0], tile[1]), self.game.get_color(tile[0], tile[1]))))) \
                and (not self.game.get_char(tile[0], tile[1]) == 46 or self.game.is_doorway(tile[0], tile[1])):
            return True
        else:
            return False

    def sort_key_func(self, tile):
        tile_nbh = self.game.neighbors_8_dir(tile[0], tile[1])
        glyph = self.game.get_glyph(tile[0], tile[1])
        count = 0
        for i in tile_nbh:
            if self.game.get_glyph(i[0], i[1]) == glyph:
                count += 1
        return -count

    # metodo che se possibile sposta l'agente nella casella adiacente con/senza(equal) il glifo corrispondente
    def roam_to_next_glyph(self, glyph, equal):
        char = glyph[0]
        color = glyph[1]
        rew = 0
        done = False
        info = None

        agent = self.game.get_agent_position()
        near = self.game.neighbors_4_dir(agent[0], agent[1])
        near.sort(key=self.sort_key_func)

        dummy = self.game.neighbors_8_dir(agent[0], agent[1])
        for i in near:
            dummy.remove(i)
        dummy.sort(key=self.sort_key_func)

        near.extend(dummy)

        while len(near) > 0:
            next = near.pop(0)
            char_n = self.game.get_char(next[0], next[1])
            color_n = self.game.get_char(next[0], next[1])
            if self.game.is_unexplored(next[0], next[1]) and (glyph is None or
                                                              (not equal and (char_n, color_n) != (char, color)) or
                                                              (equal and (char_n, color_n) == (char, color)) or
                                                              char_n == 96 or
                                                              char_n == 37 or
                                                              char_n == 36) \
                    and self.game.is_walkable(next[0], next[1]):
                agent = self.game.get_agent_position()
                rew, done, info = self.game.do_it(self.game.move_translator(agent[0], agent[1], next[0], next[1]), None)
                if self.game.update_agent():
                    message = self.game.get_parsed_message()
                    if message.__contains__("It's solid stone.") or \
                            message.__contains__("It's a wall.") or \
                            message.__contains__("You can't move diagonally into an intact doorway.") or \
                            message.__contains__("You try to move the boulder, but in vain.") or \
                            message.__contains__("Perhaps that's why you cannot move it.") or \
                            message.__contains__("You hear a monster behind the boulder."):
                        self.game.append_exception(next)
                        return 0, rew, done, info
                    return 1, rew, done, info
        return 0, rew, done, info

    # metodo per seguire un percorso di glifi '#'(corridoio) ignoti fino ad esaurirli
    def corridor_roamer(self):
        last_roam = 1
        info = None
        done = False
        rew = 0
        found_another = False
        while last_roam == 1 and not self.eject_button():
            last_roam, rew, done, info = self.roam_to_next_glyph((35, 7), True)

        # se il corridoio ?? terminato regolarmente
        if last_roam == 0:
            # se non ?? presente un'uscita esegui 'search' 20 volte
            last_roam, rew, done, info = self.roam_to_next_glyph((35, 7), False)
            i = 0
            agent = self.game.get_agent_position()
            while last_roam == 0 and i < 30 and not done and not self.game.get_parsed_message().__contains__("You find") \
                    and not self.game.unexplored_walkable_around(agent[0], agent[1]) \
                    and not 3 <= self.game.get_bl_stats()[21] <= 4:

                if not self.game.update_agent():
                    return False, rew, True
                if self.eject_button():
                    return False, rew, done
                if not game.get_fast_mode():
                    print("search in suspect corridor end... try:", i)
                rew, done, info = self.game.do_it(75, None)  # search
                i += 1
                # prova a spostarsi in una casella '#' appena scoperta
                if not done:
                    last_roam, rew, done, info = self.roam_to_next_glyph((35, 7), True)
                if last_roam != 1 and not done:
                    # se non riesce effettua due passi in caselle adiacenti ignote
                    last_roam, rew, done, info = self.roam_to_next_glyph((35, 7), False)
                    if done == True:
                        break
                    last_roam, rew, done, info = self.roam_to_next_glyph((35, 7), False)
                else:
                    # se riesce dovr?? seguire anche il nuovo corridoio appena individuato
                    found_another = True
                    break
                agent = self.game.get_agent_position()
        else:
            return False, rew, done

        return True, rew, done

    def planning(self, stats, safe_play, agent):
        path, coords = self.mixed_plan([(35, 15), (35, 7), (46, 7), (45, 3), (124, 3), (43, 3)],
                                        self.condition_multiple_obj_v0, safe_play)
        if path is None or len(path) == 0:
            return None, None, None
        else:
            char = game.get_char(coords[0], coords[1])
            color = game.get_color(coords[0], coords[1])
            if char == 43 and color == 3:
                self.chosen_task = "reach_doorway_closed"
                return "reach_doorway_closed", path, coords
            elif char == 35:
                self.chosen_task = "corridor_roam"
                return "corridor_roam", path, coords
            else:
                self.chosen_task = "reach_doorway_open"
                return "reach_doorway_open", path, coords

    def execution(self, path, arg1, agent, stats):
        if self.chosen_task == "reach_doorway_open":
            rew, done, info = self.do_plan(path)
            if rew == -1:
                game.clear_memory(arg1[0], arg1[1])
                return rew, done, info
            j = 0
            while game.is_near_glyph(agent[0], agent[1], (32, 0),
                                           4) and not self.eject_button() and j < 40 and not done and not game.get_parsed_message().__contains__(
                "You find"):  # when near void

                if 3 <= stats[21] <= 4:
                    break

                if not game.get_fast_mode():
                    print("searching on the void... try: ", j)
                rew, done, info = game.do_it(75, None)  # search
                agent = game.get_agent_position()
                stats = game.get_bl_stats()
                j += 1
            return rew, done, info

        elif self.chosen_task == "reach_doorway_closed":
            rew, done, info = self.do_plan(path)
            if game.get_parsed_message().__contains__(" no door"):
                # self.game.append_exception((arg1[0], arg1[1]))
                return rew, done, info
            if rew == -1:
                game.clear_memory(arg1[0], arg1[1])
                return rew, done, info
            if game.get_parsed_message().__contains__("Something is written here in the dust."):
                game.append_exception((arg1[0], arg1[1]))
                return rew, done, info
            if not done and rew != -1 and not game.get_parsed_message().__contains__(
                    "This door is already open.") and not game.get_parsed_message().__contains__("inventory"):
                door_direction = game.move_translator(agent[0], agent[1], arg1[0], arg1[1])
                rew, done, info = game.do_it(57, door_direction)  # open
                while not done and not self.eject_button() and game.get_parsed_message().__contains__(
                        "This door is locked.") or game.get_parsed_message().__contains__("WHAMMM!!!") \
                        or game.get_parsed_message().__contains__("The door resists!"):
                    rew, done, info = game.do_it(48, door_direction)  # kick
                game.clear_memory(arg1[0], arg1[1])
            return rew, done, info

        elif self.chosen_task == "corridor_roam":
            rew, done, info = self.do_plan(path)
            if rew == -1:
                game.clear_memory(arg1[0], arg1[1])
                return rew, done, info
            if not done and rew != -1:
                out = self.corridor_roamer()
                rew = out[1]
                done = out[2]

            return rew, done, info


class Fight(Task):
    def __init__(self, dungeon_walker, game, task_name):
        super().__init__(dungeon_walker, game, task_name)

    @staticmethod
    def condition_close_obj(tile, args):
        condition = args[0]
        range = args[1]
        center = args[2]
        if abs(tile[0] - center[0]) <= range and abs(tile[1] - center[1]) <= range:
            if condition(tile[0], tile[1]):
                return True
        return False

    # metodo ausiliario per la ricerca e il pathfinding verso un gruppo di obbiettivi in un range limitato
    def close_plan(self, not_reach_diag, condition, range, safe_play):
        path = None
        y = -1
        x = -1
        agent = self.game.get_agent_position()
        found, y, x = self.game.find(self.condition_close_obj, [condition, range, agent])
        if found:
            char = self.game.get_char(y, x)
            color = self.game.get_color(y, x)
            if not game.get_fast_mode():
                print("monster info -> char: ", char, " - color: ", color)
            if self.game.get_parsed_message().__contains__("statue"):
                self.game.append_monster_exception((y, x))
            lms = self.game.get_last_monster_searched()
            if lms[0] == char and lms[1] == \
                    color:
                self.game.update_last_monster_searched(char, color, lms[2] + 1)
                if lms[2] > 7:  # probabile statua
                    self.game.monster_exception.append((y, x))
            else:
                self.game.update_last_monster_searched(char, color, 1)

            agent = self.game.get_agent_position()
            if abs(agent[0] - y) <= 1 and (agent[1] - x) <= 1:
                return [], (y, x)
            ny = -1
            nx = -1
            near = self.game.neighbors_8_dir(y, x)
            while len(near) > 0:
                next = near.pop()
                if self.game.is_walkable(next[0], next[1]):
                    ny = next[0]
                    nx = next[1]
                    break
            path = self.dungeon_walker.path_finder(ny, nx, not_reach_diag, safe_play)
            self.game.update_memory(y, x)
        return path, (y, x)

    def planning(self, stats, safe_play, agent):
        path, coords = self.close_plan(False, game.is_a_monster, 5, False)
        if path is None:
            return None, None, None
        else:
            return self.name, path, coords

    def execution(self, path, arg1, agent, stats):
        length = len(path)
        y_dist = abs(arg1[0] - agent[0])
        x_dist = abs(arg1[1] - agent[1])
        rew = 0
        done = False
        info = None
        if y_dist >= 3 and x_dist >= 5 and length > 0 and not done:
            if game.update_agent():
                rew, done, info = game.do_it(path.pop(), None)
            else:
                return 0, True, None
        elif y_dist == 2 or x_dist == 2 and not done:
            rew, done, info = game.do_it(75, None)  # Wait - searching
        elif not done:
            direction = game.move_translator(agent[0], agent[1], arg1[0], arg1[1])
            game.do_it(direction, None)  # attack

            message = game.get_parsed_message()
            act = game.get_act_num()
            if message.__contains__("kill"):  # mostri rimossi: dwarf
                if message.__contains__("fox"):
                    game.append_recently_killed(("fox", act, arg1[0], arg1[1]))
                elif message.__contains__("jackal"):
                    game.append_recently_killed(("jackal", act, arg1[0], arg1[1]))
                elif message.__contains__("acid blob"):
                    game.append_recently_killed(("acid blob", act, arg1[0], arg1[1]))
                elif message.__contains__("coyote"):
                    game.append_recently_killed(("coyote", act, arg1[0], arg1[1]))
                elif message.__contains__("dog"):
                    game.append_recently_killed(("dog", act, arg1[0], arg1[1]))
                elif message.__contains__("kitten"):
                    game.append_recently_killed(("kitten", act, arg1[0], arg1[1]))
                elif message.__contains__("pony"):
                    game.append_recently_killed(("pony", act, arg1[0], arg1[1]))
                elif message.__contains__("rat"):
                    game.append_recently_killed(("rat", act, arg1[0], arg1[1]))
                elif message.__contains__("gnome"):
                    game.append_recently_killed(("gnome", act, arg1[0], arg1[1]))
                elif message.__contains__("hobbit"):
                    game.append_recently_killed(("hobbit", act, arg1[0], arg1[1]))
                elif message.__contains__("goblin"):
                    game.append_recently_killed(("goblin", act, arg1[0], arg1[1]))
                elif message.__contains__("newt"):
                    game.append_recently_killed(("newt", act, arg1[0], arg1[1]))
                elif message.__contains__("floating eye"):
                    game.append_recently_killed(("floating eye", act, arg1[0], arg1[1]))
                elif message.__contains__("rothe"):
                    game.append_recently_killed(("rothe", act, arg1[0], arg1[1]))
                elif message.__contains__("gecko"):
                    game.append_recently_killed(("gecko", act, arg1[0], arg1[1]))
                elif message.__contains__("iguana"):
                    game.append_recently_killed(("iguana", act, arg1[0], arg1[1]))
                elif message.__contains__("mold"):
                    game.append_recently_killed(("mold", act, arg1[0], arg1[1]))
                elif message.__contains__("mole"):
                    game.append_recently_killed(("mole", act, arg1[0], arg1[1]))
                elif message.__contains__("orc"):
                    game.append_recently_killed(("orc", act, arg1[0], arg1[1]))
                elif message.__contains__("shrieker"):
                    game.append_recently_killed(("shrieker", act, arg1[0], arg1[1]))
                elif message.__contains__("goblin"):
                    game.append_recently_killed(("goblin", act, arg1[0], arg1[1]))
                elif message.__contains__("ant"):
                    game.append_recently_killed(("ant", act, arg1[0], arg1[1]))
        return rew, done, info


class Gold(ReachTask):
    def __init__(self, dungeon_walker, game, task_name):
        super().__init__(dungeon_walker, game, task_name)

    def planning(self, stats, safe_play, agent):
        path, coords = self.standard_plan([(36, -1)], False, safe_play)
        if path is None or len(path) == 0:
            return None, None, None
        else:
            return self.name, path, coords


class Eat(Task):
    def __init__(self, dungeon_walker, game, task_name):
        super().__init__(dungeon_walker, game, task_name)

    def fresh_food(self):
        message = self.game.get_parsed_message()
        stats = self.game.get_bl_stats()
        for log in self.game.get_recently_killed():
            monster = log[0]
            turn = log[1]
            if abs(turn - self.game.get_act_num()) < 50 and message.__contains__(monster):
                if message.__contains__("yellow mold"):
                    return False
                if message.__contains__("acid blob") and stats[10] < 20:
                    return False
                return True
        return False

    def planning(self, stats, safe_play, agent):
        if stats[21] < 1:
            return None, None, None
        path, coords = self.standard_plan([(37, -1)], False, safe_play)
        if path is None or len(path) == 0:
            return None, None, None
        else:
            return self.name, path, coords

    def execution(self, path, arg1, agent, stats):
        rew, done, info = self.do_plan(path)
        if rew == -1:
            game.clear_memory(arg1[0], arg1[1])
            return None, None, None
        agent = game.get_agent_position()
        stats = game.get_bl_stats()
        parsed_all = game.parse_all()
        gnam = False
        if parsed_all.__contains__("kobold") or \
                parsed_all.__contains__("rabid") or \
                parsed_all.__contains__("soldier ant") or \
                parsed_all.__contains__("homunculus"):
            game.append_inedible((arg1[0], arg1[1]))
            return None, None, None
        elif parsed_all.__contains__("You see here a lichen corpse.") or \
                parsed_all.__contains__("ration") or \
                parsed_all.__contains__("melon") or \
                parsed_all.__contains__("apple") or \
                parsed_all.__contains__("gunyoki") or \
                parsed_all.__contains__("pear") or \
                parsed_all.__contains__("leaf") or \
                parsed_all.__contains__("carrot") or \
                parsed_all.__contains__("garlic") or \
                parsed_all.__contains__("meat") or \
                parsed_all.__contains__("egg") or \
                parsed_all.__contains__("orange") or \
                parsed_all.__contains__("banana") or \
                parsed_all.__contains__("wafer") or \
                parsed_all.__contains__("candy") or \
                parsed_all.__contains__("cookie") or \
                parsed_all.__contains__("jelly") or \
                parsed_all.__contains__("pie") or \
                parsed_all.__contains__("pancake") or \
                parsed_all.__contains__("wolfsbane") or \
                parsed_all.__contains__("tin") or \
                parsed_all.__contains__("kelp frond") or \
                parsed_all.__contains__("You see here a lizard corpse.") or self.fresh_food():
            game.do_it(35, None)  # eat
            gnam = True
            message = game.get_parsed_message()
            if message.__contains__("eat") and message.__contains__("?"):
                env.step(7)  # yes
                gnam = True
        elif stats[21] == 4:
            game.reset_inedible()
            game.do_it(35, None)  # eat
            gnam = True
            message = game.get_parsed_message()
            if message.__contains__("eat") and message.__contains__("?"):
                env.step(7)  # yes
                gnam = True
        if not gnam:
            game.append_inedible((arg1[0], arg1[1]))
        return None, None, None


class Horizon(ReachTask):
    def __init__(self, dungeon_walker, game, task_name):
        super().__init__(dungeon_walker, game, task_name)

    def condition_horizon_obj(self, tile, args):
        glyph = args[0]
        char = glyph[0]
        color = glyph[1]
        if self.game.get_char(tile[0], tile[1]) == char:  # and self.color_obs[tile[0]][tile[1]] == color: wip
            if self.game.is_near_glyph(tile[0], tile[1], (32, 0), 8) and self.game.is_unexplored(tile[0], tile[1]):
                return True
        return False

    def horizon_plan(self, glyph, safe_play):
        found, y, x = self.game.find(self.condition_horizon_obj, glyph)
        if found:
            path = self.dungeon_walker.path_finder(y, x, False, safe_play)
            self.game.update_memory(y, x)
            return path, (y, x)
        return None, (-1, -1)

    def planning(self, stats, safe_play, agent):
        path, coords = self.horizon_plan([(46, 7)], safe_play)
        if path is None:
            return None, None, None
        else:
            return self.name, path, coords


class Unseen(ReachTask):
    def __init__(self, dungeon_walker, game, task_name):
        super().__init__(dungeon_walker, game, task_name)

    def condition_unexplored_obj(self, tile, args):
        char = -1
        color = -1
        glyph = args[0]
        if glyph is not None:
            char = glyph[0]
            color = glyph[1]
        isolated = args[1]
        if self.game.get_memory(tile[0], tile[1]) == -1 and \
                (glyph is None and self.game.is_walkable(tile[0], tile[1])) or (
                char == self.game.get_char(tile[0], tile[1])
                and color == self.game.get_color(tile[0], tile[1])
                and (not isolated or self.game.is_isolated(tile[0], tile[1], glyph, True))):
            return True
        else:
            return False

    # metodo ausiliario per la ricerca e il pathfinding verso un obbiettivo inesplorato/isolato
    def unexplored_plan(self, glyph, not_reach_diag, isolated, safe_play):
        found, y, x = self.game.find(self.condition_unexplored_obj, [glyph, isolated])
        if found:
            path = self.dungeon_walker.path_finder(y, x, not_reach_diag, safe_play)
            self.game.update_memory(y, x)
            return path, (y, x)
        return None, (-1, -1)

    def planning(self, stats, safe_play, agent):
        path, coords = self.unexplored_plan(None, False, False, safe_play)
        if path is None or len(path) == 0:
            return None, None, None
        else:
            return self.name, path, coords


class HiddenRoom(HiddenTask):
    def __init__(self, dungeon_walker, game, task_name):
        super().__init__(dungeon_walker, game, task_name)

    def planning(self, stats, safe_play, agent):
        if 3 <= stats[21] <= 4:
            return None, None, None
        path, coords = self.unsearched_plan([(46, 7)], safe_play)
        if path is None or len(path) == 0:
            return None, None, None
        else:
            return "search_hidden", path, coords


class HiddenCorridor(HiddenTask):
    def __init__(self, dungeon_walker, game, task_name):
        super().__init__(dungeon_walker, game, task_name)

    def planning(self, stats, safe_play, agent):
        if 3 <= stats[21] <= 4:
            return None, None, None
        path, coords = self.unsearched_plan([(35, 7)], safe_play)
        if path is None or len(path) == 0:
            return None, None, None
        else:
            return "search_hidden", path, coords


class Break(Task):
    def __init__(self, dungeon_walker, game, task_name):
        super().__init__(dungeon_walker, game, task_name)

    def planning(self, stats, safe_play, agent):
        near = game.neighbors_8_dir(agent[0], agent[1])
        for tile in near:
            if game.is_a_monster(tile[0], tile[1]):
                return None, None, None
        if stats[21] <= 2 and game.get_risk(agent[0], agent[1]) == 0 and stats[11] != 0 and (
                stats[10] / stats[11]) < 0.65:
            return self.name, None, None

    def execution(self, path, arg1, agent, stats):
        rew, done, info = game.do_it(38, None)  # esc, per evitare strane situe
        if not done:
            rew, done, info = game.do_it(75, None)  # search per aspettare con value
            agent = game.get_agent_position()
            message = game.get_parsed_message()
            if message.__contains__("hit") or \
                message.__contains__("bite") or \
                message.__contains__("attack") or \
                message.__contains__("throw") or \
                message.__contains__("swing"):
                game.force_risk(agent[0], agent[1], 2)
        return rew, done, info


# metodo che pianifica la task da eseguire in un dato stato
def planning(game, tasks_prio, task_map):

    if game.get_new_turn() == game.get_old_turn() :
        game.stuck()
    else:
        game.reset_stuck_counter()

    if not game.update_agent():
        return "failure", None, None
    else:
        game.update_obs()

    stats = game.get_bl_stats()
    safe_play = game.get_safe_play()
    agent = game.get_agent_position()

    while len(tasks_prio) > 0:
        task_name = tasks_prio.pop(0)
        task = task_map[task_name]

        out = task.planning(stats, safe_play, agent)
        if out is not None:
            task_name_o = out[0]
            path = out[1]
            arg1 = out[2]
            if task_name_o is not None:
                return task_name, path, arg1

    return "failure", None, None


# metodo che esegue le task pianificata
def main_logic(dungeon_walker, game, tasks_prio, task_map, attempts):
    success = 0
    scores = []
    mediana = 0

    for i in range(0, attempts):

        if game.get_fast_mode():
            if game.get_act_num != 0 and i != 0:
                scores.append(game.get_actual_score())
                size = len(scores)
                center = math.floor(size / 2)
                scores.sort()
                if (size % 2) == 1:
                    mediana = scores[center]
                else:
                    mediana = (scores[center] + scores[center - 1]) / 2

        done = False
        game.reset_hard_search_num()
        rew = 0
        game.reset_game()
        game.reset_stuck_counter()

        if game.get_fast_mode():
            go_back(3)
            true_divisor = i
            if true_divisor == 0:
                true_divisor = 1
            face = "(???_???)"
            if mediana < 475 and i != 0:
                face = "(???????????????)"
            if mediana >= 681:
                face = "(???'-')???"
            if mediana >= 756:
                face = "???(`?????)???"
            print("// mean score: ", game.get_total_score() / true_divisor, "// median: ", mediana, " // games: ",
                  len(scores), "      ", face, "               ")
            print(scores)

        while not done:
            task, path, arg1 = planning(game, tasks_prio.copy(), task_map)
            if not game.get_fast_mode():
                print("TASK: ", task, " PATH: ", path)

            if not game.update_agent() or game.get_stuck_counter() > 200:
                break

            agent = game.get_agent_position()
            stats = game.get_bl_stats()

            if task == "failure":
                hs_n = game.get_hard_search_num()
                if not game.update_agent() or hs_n > 200:
                    break
                elif hs_n > 20:
                    dungeon_walker.panic = True
                if hs_n % 2 == 0 and hs_n != 0:
                    game.reset_memory()
                game.hard_search()
                game.increment_hard_search_num()
                rew, done, info = game.do_it(75, None)  # search per aspettare con value
            else:
                rew, done, info = task_map[task].execution(path, arg1, agent, stats)

        if rew == 1:
            success += 1


def go_back(num_lines):  # funzione per sovrascrivere lo schermo attuale
    print("\033[%dA" % num_lines)


def start_bot():
    with open('config.json', 'r') as f:
        config = json.load(f)

    print("\nJudy is looking for the Amulet of Yendor on the map ...\n")

    exec_mode = config['fast_mode']
    mode = False
    if exec_mode == "on":
        mode = True
        print("\nFast_Mode : ON")
    elif exec_mode == "off":
        print("\nFast_Mode : OFF")
    else:
        print("\nFast_Mode can only be \"on\" or \"off\" -> value set to default : OFF")
    time.sleep(0.5)

    attempts = 100
    try:
        attempts = int(config['attempts'])
        print("Attempts : ", attempts)
    except:
        print("Attempts must be an int value -> value set to default : ", attempts)
        attempts = 100
    time.sleep(0.5)

    game = GameWhisperer(mode)
    dungeon_walker = DungeonWalker(game)

    task_prio = config['task_prio_list']
    task_map = {}
    for i in range(0, len(task_prio)):
        task = task_prio[i]
        if task == "pray":
            task_map[task] = Pray(dungeon_walker, game, task)
        elif task == "take_a_break":
            task_map[task] = Break(dungeon_walker, game, task)
        elif task == "engrave_elbereth":
            task_map[task] = Elbereth(dungeon_walker, game, task)
        elif task == "run_for_your_life":
            task_map[task] = Run(dungeon_walker, game, task)
        elif task == "close_monster_fight":
            task_map[task] = Fight(dungeon_walker, game, task)
        elif task == "time_of_the_lunch":
            task_map[task] = Eat(dungeon_walker, game, task)
        elif task == "greed_of_gold":
            task_map[task] = Gold(dungeon_walker, game, task)
        elif task == "stairs_descent":
            task_map[task] = StairsDescent(dungeon_walker, game, task)
        elif task == "stairs_ascent":
            task_map[task] = StairsAscent(dungeon_walker, game, task)
        elif task == "reach_closest_explorable":
            task_map[task] = ExploreClosest(dungeon_walker, game, task)
        elif task == "reach_horizon":
            task_map[task] = Horizon(dungeon_walker, game, task)
        elif task == "search_hidden_room":
            task_map[task] = HiddenRoom(dungeon_walker, game, task)
        elif task == "explore_unseen":
            task_map[task] = Unseen(dungeon_walker, game, task)
        elif task == "search_hidden_corridor":
            task_map[task] = HiddenCorridor(dungeon_walker, game, task)
        print(task)
        time.sleep(0.1)

    print("\nJudy is ready for YASD ...")
    print("\n\n")
    time.sleep(1)

    return dungeon_walker, game, task_prio, task_map, attempts


dungeon_walker, game, logic, map, attempts = start_bot()

main_logic(dungeon_walker, game, logic, map, attempts)
