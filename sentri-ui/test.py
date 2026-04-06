from tools.tool import AgentTools

agent_tools = AgentTools()

print("start")

agent_tools.generate_flight_path_on_id(shape="square", building_ids=[2, 6, 26])