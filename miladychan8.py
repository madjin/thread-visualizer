import argparse
import json
import requests
from bs4 import BeautifulSoup
from pyjsoncanvas import Canvas, TextNode, FileNode, LinkNode, GroupNode, Edge, Color
import hashlib

def fetch_json(url):
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')
    script_tag = soup.find('script', {'id': 'post-data'})
    
    if script_tag:
        return json.loads(script_tag.string)
    else:
        print("Could not find JSON data in the page.")
        return None

def create_simplified_json(data, is_catalog=False):
    print(json.dumps(data, indent=2))
    
    if is_catalog:
        if 'threads' in data:
            return [simplify_thread(thread) for thread in data['threads'] if thread is not None]
        else:
            print("Warning: 'threads' key not found in data")
            return []
    else:
        return simplify_thread(data) if data is not None else None

def simplify_thread(thread):
    if thread is None:
        return None
    
    print(json.dumps(thread, indent=2))
    
    simplified = {
        'id': thread.get('id'),
        'subject': thread.get('subject'),
        'body': thread.get('body'),
        'image': simplify_image(thread.get('image')) if thread.get('image') else None,
        'replies': []
    }
    
    posts = thread.get('posts', [])
    if posts:
        for post in posts:
            if post is not None:
                simplified['replies'].append({
                    'id': post.get('id'),
                    'body': post.get('body'),
                    'image': simplify_image(post.get('image')) if post.get('image') else None,
                    'links': post.get('links', [])
                })
    
    return simplified

def simplify_image(image):
    if image is None:
        return None
    
    file_extension = 'jpg' if image.get('file_type') == 0 else 'png' if image.get('file_type') == 1 else 'webm' if image.get('file_type') == 3 else 'unknown'
    return {
        'src': f"https://boards.miladychan.org/assets/images/src/{image.get('sha1')}.{file_extension}",
        'thumb': f"https://boards.miladychan.org/assets/images/thumb/{image.get('sha1')}.webp",
        'width': image.get('dims', [0, 0, 0, 0])[0],
        'height': image.get('dims', [0, 0, 0, 0])[1],
        'thumb_width': image.get('dims', [0, 0, 0, 0])[2],
        'thumb_height': image.get('dims', [0, 0, 0, 0])[3],
        'video': image.get('video', False)
    }

def position_nodes_spaced(canvas, node_map, node_id, x, y, level=0, vertical_spacing=100, horizontal_spacing=300):
    node_data = node_map[node_id]
    main_node = node_data['nodes'][0]
    main_node.x = x
    main_node.y = y

    if isinstance(main_node, GroupNode):
        text_node = node_data['nodes'][1]
        img_node = node_data['nodes'][2]
        text_node.x = main_node.x
        text_node.y = main_node.y
        img_node.x = main_node.x + text_node.width + 5
        img_node.y = main_node.y

    current_y = y + main_node.height + vertical_spacing

    for i, reply_id in enumerate(node_data['replies']):
        reply_node_data = node_map[reply_id]
        reply_main_node = reply_node_data['nodes'][0]
        
        reply_x = x + (i % 3) * horizontal_spacing  # Distribute replies horizontally
        reply_y = position_nodes_spaced(canvas, node_map, reply_id, reply_x, current_y, level+1, vertical_spacing, horizontal_spacing)
        
        # Add edge from parent to child
        canvas.add_edge(Edge(fromNode=main_node.id, toNode=reply_main_node.id, fromSide="bottom", toSide="top"))
        
        current_y = reply_y + vertical_spacing

    return current_y

def create_canvas(data, spaced=False):
    canvas = Canvas(nodes=[], edges=[])
    node_map = {}

    op_nodes = create_post_node(data['body'], data['image'], 0, 0, data['id'])
    for node in op_nodes:
        canvas.add_node(node)
    node_map[data['id']] = {'nodes': op_nodes, 'replies': []}

    for reply in data['replies']:
        reply_nodes = create_post_node(reply['body'], reply['image'], 0, 0, reply['id'])
        for node in reply_nodes:
            canvas.add_node(node)
        node_map[reply['id']] = {'nodes': reply_nodes, 'replies': []}

        parent_id = data['id']  # Default to OP
        if reply['links']:
            potential_parent_id = reply['links'][0]['id']
            if potential_parent_id in node_map:
                parent_id = potential_parent_id

        node_map[parent_id]['replies'].append(reply['id'])

    if spaced:
        position_nodes_spaced(canvas, node_map, data['id'], 0, 0)
    else:
        position_nodes(canvas, node_map, data['id'], 0, 0)

    return canvas

def create_post_node(text, image, x, y, node_id):
    if image:
        text_node = create_text_node(text, 0, 0, f"{node_id}-text")
        img_node = create_image_node(image, text_node.width + 10, 0, f"{node_id}-img")
        
        group_width = text_node.width + img_node.width + 20
        group_height = max(text_node.height, img_node.height) + 20
        
        group = GroupNode(
            id=str(node_id),
            x=x,
            y=y,
            width=group_width,
            height=group_height,
            label=f"Post {node_id}"
        )
        
        return [group, text_node, img_node]
    else:
        return [create_text_node(text, x, y, node_id)]

def create_text_node(text, x, y, node_id):
    lines = text.split('\n')
    width = max(len(line) * 7 for line in lines)  # Estimating 7 pixels per character
    height = len(lines) * 20  # Estimating 20 pixels per line
    return TextNode(
        id=str(node_id),
        x=x,
        y=y,
        width=max(250, min(width, 500)),  # Minimum 250, maximum 500
        height=max(100, min(height, 300)),  # Minimum 100, maximum 300
        text=text
    )

def create_image_node(image, x, y, node_id):
    if image['video']:
        return LinkNode(
            id=str(node_id),
            x=x,
            y=y,
            width=image['thumb_width'],
            height=image['thumb_height'],
            url=image['src']
        )
    else:
        return FileNode(
            id=str(node_id),
            x=x,
            y=y,
            width=image['thumb_width'],
            height=image['thumb_height'],
            file=image['src']
        )

def position_nodes(canvas, node_map, node_id, x, y):
    node_data = node_map[node_id]
    main_node = node_data['nodes'][0]
    main_node.x = x
    main_node.y = y

    if isinstance(main_node, GroupNode):
        # Position text and image nodes within the group
        text_node = node_data['nodes'][1]
        img_node = node_data['nodes'][2]
        text_node.x = main_node.x
        text_node.y = main_node.y
        img_node.x = main_node.x + text_node.width + 10
        img_node.y = main_node.y

    current_y = y + main_node.height + 20  # Add padding between nodes

    # Position replies
    for reply_id in node_data['replies']:
        reply_node_data = node_map[reply_id]
        reply_main_node = reply_node_data['nodes'][0]
        reply_y = position_nodes(canvas, node_map, reply_id, x + 50, current_y)
        canvas.add_edge(Edge(fromNode=main_node.id, toNode=reply_main_node.id, fromSide="bottom", toSide="top"))
        current_y = reply_y

    return current_y

def main():
    parser = argparse.ArgumentParser(description="Process miladychan JSON data")
    parser.add_argument("url", help="URL of the catalog or thread")
    parser.add_argument("-c", "--canvas", action="store_true", help="Output in Canvas format")
    parser.add_argument("-s", "--spaced", action="store_true", help="Use spaced layout for better readability")
    args = parser.parse_args()

    json_data = fetch_json(args.url)
    if not json_data:
        return

    is_catalog = 'catalog' in args.url
    simplified_data = create_simplified_json(json_data, is_catalog)

    if simplified_data is None:
        print("No valid data found.")
        return

    if args.canvas:
        if is_catalog:
            # Handle catalog case
            for thread in simplified_data:
                canvas = create_canvas(thread, spaced=args.spaced)
                print(canvas.to_json())
        else:
            canvas = create_canvas(simplified_data, spaced=args.spaced)
            print(canvas.to_json())
    else:
        print(json.dumps(simplified_data, indent=2))

if __name__ == "__main__":
    main()
