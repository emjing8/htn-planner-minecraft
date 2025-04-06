import json
import copy
import pyhop

def op_done_producing(state, item):
    if hasattr(state, 'in_production') and item in state.in_production:
        state.in_production.remove(item)
    return state

def check_enough(state, ID, item, num):
    if getattr(state, item)[ID] >= num:
        return []
    return False

def produce_enough(state, ID, item, num):
    return [('produce', ID, item), ('have_enough', ID, item, num)]

def produce(state, ID, item):
    if not hasattr(state, 'depth'):
        state.depth = {}
    if ID not in state.depth:
        state.depth[ID] = 0
    if state.depth[ID] >= 300:
        return False
    state.depth[ID] += 1

    if not hasattr(state, 'in_production'):
        state.in_production = set()
    if item in state.in_production:
        return False

    state.in_production.add(item)
    return [('produce_' + item, ID), ('op_done_producing', item)]


def make_method(recipe_name, rule, product):
    if product in rule.get('Requires', {}):
        return None

    def method(state, ID):
        subtasks = []

        for (req_item, req_amt) in rule.get('Requires', {}).items():
            subtasks.append(('have_enough', ID, req_item, req_amt))

        for (cons_item, cons_amt) in rule.get('Consumes', {}).items():
            subtasks.append(('have_enough', ID, cons_item, cons_amt))

        op_name = 'op_' + recipe_name.replace(' ', '_')
        subtasks.append((op_name, ID))
        return subtasks

    method.__name__ = 'produce_' + recipe_name.replace(' ', '_')
    return method


def compute_relevance(data):

    relevant = set(data['Goal'].keys())
    changed = True
    while changed:
        changed = False
        for rule in data['Recipes'].values():

            if any(p in relevant for p in rule.get('Produces', {})):
                needed = set(rule.get('Requires', {}).keys()) | set(rule.get('Consumes', {}).keys())
                for x in needed:
                    if x not in relevant:
                        relevant.add(x)
                        changed = True
    return relevant

def prune_irrelevant_recipes(data):
    relevant = compute_relevance(data)
    new_recipes = {}
    for (rname, rule) in data['Recipes'].items():
        produces = set(rule.get('Produces', {}).keys())
        if produces & relevant:
            new_recipes[rname] = rule
    data['Recipes'] = new_recipes


def domain_heuristic(state, curr_task, tasks, plan, depth, stack):
    if depth > 300:
        return True
    if state.time['agent'] > DOMAIN_DATA['TimeBound']:
        return True
    return False


def declare_methods(data):

    pyhop.methods = {}

    pyhop.declare_methods('have_enough', check_enough, produce_enough)
    pyhop.declare_methods('produce', produce)
    
    methods_by_item = {}
    for recipe_name, recipe in data['Recipes'].items():
        for product in recipe.get('Produces', {}):
            taskname = 'produce_' + product
            if taskname not in methods_by_item:
                methods_by_item[taskname] = []
            m = make_method(recipe_name, recipe, product)
            if m:
                methods_by_item[taskname].append(m)

    for taskname, ml in methods_by_item.items():
        ml.reverse()
        pyhop.declare_methods(taskname, *ml)



def make_operator(recipe_name, rule):
    def operator(state, ID):
        global DOMAIN_DATA

        for (req_item, req_amt) in rule.get('Requires', {}).items():
            if getattr(state, req_item)[ID] < req_amt:
                return False
        for (cons_item, cons_amt) in rule.get('Consumes', {}).items():
            if getattr(state, cons_item)[ID] < cons_amt:
                return False


        new_time = state.time[ID] + rule.get('Time', 0)
        if new_time > DOMAIN_DATA.get('TimeBound', 9999999):
            return False
        state.time[ID] = new_time


        for (p_item, p_amt) in rule.get('Produces', {}).items():
            getattr(state, p_item)[ID] += p_amt

        for (c_item, c_amt) in rule.get('Consumes', {}).items():
            getattr(state, c_item)[ID] -= c_amt

        return state

    operator.__name__ = 'op_' + recipe_name.replace(' ', '_')
    return operator

def declare_operators(data):
    global DOMAIN_DATA
    DOMAIN_DATA = data

    ops = [op_done_producing]
    for (rname, rule) in data['Recipes'].items():
        ops.append(make_operator(rname, rule))
    pyhop.declare_operators(*ops)

def set_up_state(data, ID, time=0):
    s = pyhop.State('init_state')
    s.time = {ID: time}
    for it in data.get('Items', []):
        setattr(s, it, {ID: 0})
    for t in data.get('Tools', []):
        setattr(s, t, {ID: 0})
    for (k, v) in data.get('Initial', {}).items():
        if hasattr(s, k):
            getattr(s, k)[ID] = v
        else:
            setattr(s, k, {ID: v})
    return s

def set_up_goals(data, ID):
    tasks = []
    for (item, amt) in data.get('Goal', {}).items():
        tasks.append(('have_enough', ID, item, amt))
    return tasks


def add_base_recipes(data):
    # Fallback plans:
    data['Recipes']['mine ore'] = {
        'Produces': {'ore': 1},
        'Time': 3
    }
    data['Recipes']['mine cobble'] = {
        'Produces': {'cobble': 1},
        'Time': 2
    }
    data['Recipes']['mine coal'] = {
        'Produces': {'coal': 1},
        'Time': 3
    }
    produced = set()
    for rule in data['Recipes'].values():
        for i in rule.get('Produces', {}):
            produced.add(i)
    if 'iron_pickaxe' not in produced:
        data['Recipes']['craft iron_pickaxe at bench'] = {
            'Produces': {'iron_pickaxe': 1},
            'Requires': {'bench': 1},
            'Consumes': {'ingot': 3, 'stick': 2},
            'Time': 1
        }
    if 'wooden_pickaxe' not in produced:
        data['Recipes']['craft wooden_pickaxe'] = {
            'Produces': {'wooden_pickaxe': 1},
            'Consumes': {'plank': 3, 'stick': 2},
            'Time': 1
        }
    if 'cart' not in produced:
        data['Recipes']['craft cart'] = {
            'Produces': {'cart': 1},
            'Consumes': {'ingot': 5},
            'Time': 1
        }
    if 'rail' not in produced:
        data['Recipes']['craft rail'] = {
            'Produces': {'rail': 16},
            'Consumes': {'ingot': 6, 'stick': 1},
            'Time': 1
        }
    if 'bench' not in produced:
        data['Recipes']['craft bench'] = {
            'Produces': {'bench': 1},
            'Consumes': {'plank': 4},
            'Time': 1
        }
    if 'ingot' not in produced:
        if 'furnace' not in produced:
            data['Recipes']['craft furnace at bench'] = {
                'Produces': {'furnace': 1},
                'Requires': {'bench': 1},
                'Consumes': {'cobble': 8},
                'Time': 1
            }
        data['Recipes']['smelt ore in furnace'] = {
            'Produces': {'ingot': 1},
            'Requires': {'furnace': 1},
            'Consumes': {'coal': 1, 'ore': 1},
            'Time': 5
        }
    if 'stick' not in produced:
        if 'plank' not in produced:
            data['Recipes']['craft plank'] = {
                'Produces': {'plank': 4},
                'Consumes': {'wood': 1},
                'Time': 1
            }
        data['Recipes']['craft stick'] = {
            'Produces': {'stick': 4},
            'Consumes': {'plank': 2},
            'Time': 1
        }


def run_test(data, initial, goal, timebound, label=''):
    test_data = copy.deepcopy(data)
    test_data['Initial'] = initial
    test_data['Goal'] = goal
    test_data['TimeBound'] = timebound
    pyhop.methods = {}
    pyhop.operators = {}
    

    pyhop.declare_methods('have_enough', check_enough, produce_enough)
    pyhop.declare_methods('produce', produce)
    
    declare_operators(test_data)
    declare_methods(test_data)
    
    state = set_up_state(test_data, 'agent', time=0)
    tasks = set_up_goals(test_data, 'agent')
    
    print(f"\n=== TEST {label}: Initial={initial}, Goal={goal}, TimeBound={timebound} ===")
    plan = pyhop.pyhop(state, tasks, verbose=1)
    if plan is False:
        print("**Test failed** (no plan or recursion error).")
    else:
        print("Plan:", plan)
        print("  Final time =", state.time['agent'])
        print("  Plan length =", len(plan))
        if state.time['agent'] <= timebound:
            print("  **Success**")
        else:
            print("  **Time limit exceeded**")



if __name__ == '__main__':
    rules_filename = 'crafting.json'

    with open(rules_filename) as f:
        data = json.load(f)
    
    state = set_up_state(data, 'agent', time=239)
    goals = set_up_goals(data, 'agent')

    add_base_recipes(data)
    prune_irrelevant_recipes(data)
    declare_operators(data)
    declare_methods(data)
    # pyhop.add_check(domain_heuristic)
    pyhop.pyhop(state, goals, verbose=3)