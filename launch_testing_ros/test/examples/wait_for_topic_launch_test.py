# Copyright 2021 Open Source Robotics Foundation, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import re
import sys
import unittest

import launch
import launch.actions
import launch_ros.actions
import launch_testing.actions
import launch_testing.markers
from launch_testing_ros import WaitForTopics

import pytest

from std_msgs.msg import String


def generate_node(i: int):
    """Return node and remap the topic based on the index provided."""
    path_to_test = os.path.dirname(__file__)
    return launch_ros.actions.Node(
        executable=sys.executable,
        arguments=[os.path.join(path_to_test, 'talker.py')],
        name='demo_node_' + str(i),
        additional_env={'PYTHONUNBUFFERED': '1'},
        parameters=[{'hz': 10.0}],
        remappings=[('chatter', 'chatter_' + str(i))]
    )


@pytest.mark.launch_test
@launch_testing.markers.keep_alive
def generate_test_description():
    # 'n' changes the number of nodes and topics generated for this test
    n = 5
    description = [generate_node(i) for i in range(n)] + [launch_testing.actions.ReadyToTest()]
    return launch.LaunchDescription(description), {'count': n}


# TODO: Test cases fail on Windows debug builds
# https://github.com/ros2/launch_ros/issues/292
if os.name != 'nt':
    class TestFixture(unittest.TestCase):

        def test_topics_successful(self, count: int):
            """All the supplied topics should be read successfully."""
            topic_list = [('chatter_' + str(i), String) for i in range(count)]
            expected_topics = {'chatter_' + str(i) for i in range(count)}
            message_pattern = re.compile(r'Hello World: \d+')

            # Method 1 : Using the magic methods and 'with' keyword
            with WaitForTopics(
                topic_list, timeout=10.0, messages_received_buffer_length=10
            ) as wait_for_node_object_1:
                assert wait_for_node_object_1.topics_received() == expected_topics
                assert wait_for_node_object_1.topics_not_received() == set()
                for topic_name, _ in topic_list:
                    assert len(wait_for_node_object_1.received_messages(topic_name)) >= 1
                    message = wait_for_node_object_1.received_messages(topic_name).pop().data
                    assert message_pattern.match(message)

            # Multiple instances of WaitForNode() can be created safely as
            # their internal nodes spin in separate contexts
            # Method 2 : Manually calling wait() and shutdown()
            wait_for_node_object_2 = WaitForTopics(topic_list, timeout=10.0)
            assert wait_for_node_object_2.wait()
            assert wait_for_node_object_2.topics_received() == expected_topics
            assert wait_for_node_object_2.topics_not_received() == set()
            for topic_name, _ in topic_list:
                assert len(wait_for_node_object_1.received_messages(topic_name)) >= 1
                message = wait_for_node_object_2.received_messages(topic_name).pop().data
                assert message_pattern.match(message)
            wait_for_node_object_2.shutdown()

        def test_topics_unsuccessful(self, count: int):
            """All topics should be read except for the 'invalid_topic'."""
            topic_list = [('chatter_' + str(i), String) for i in range(count)]
            # Add a topic that will never have anything published on it
            topic_list.append(('invalid_topic', String))
            expected_topics = {'chatter_' + str(i) for i in range(count)}

            # Method 1
            with pytest.raises(RuntimeError):
                with WaitForTopics(topic_list, timeout=2.0):
                    pass

            # Method 2
            wait_for_node_object = WaitForTopics(topic_list, timeout=2.0)
            assert not wait_for_node_object.wait()
            assert wait_for_node_object.topics_received() == expected_topics
            assert wait_for_node_object.topics_not_received() == {'invalid_topic'}
            wait_for_node_object.shutdown()

        def test_callback(self, count):
            topic_list = [('chatter_' + str(i), String) for i in range(count)]
            expected_topics = {'chatter_' + str(i) for i in range(count)}

            # Method 3 : Using a callback function

            # Using a list to store the callback function's argument as it is mutable
            is_callback_called = [False]

            def callback(node, arg):
                node.get_logger().info(f'Callback function called with argument: {arg[0]}')
                arg[0] = True

            wait_for_node_object = WaitForTopics(topic_list, timeout=2.0, callback=callback)
            assert wait_for_node_object.wait(is_callback_called)
            assert wait_for_node_object.topics_received() == expected_topics
            assert wait_for_node_object.topics_not_received() == set()
            assert is_callback_called[0]
