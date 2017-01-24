from __future__ import print_function
import contextlib
import datetime
import sys
import time

from fabric.context_managers import settings
from pyVmomi import vim

from vcdriver.exceptions import (
    TooManyObjectsFound,
    NoObjectFound,
    TimeoutError
)


def get_vcenter_object(connection, object_type, name):
    """
    Find a vcenter object
    :param connection: A vcenter connection
    :param object_type: A vcenter object type, like vim.Folder
    :param name: The name of the object

    :return: The object found

    :raise: TooManyObjectsFound: If more than one object is found
    :raise: NoObjectFound: If no results are found
    """
    content = connection.RetrieveContent()
    view = content.viewManager.CreateContainerView
    objects = [
        obj for obj in view(content.rootFolder, [object_type], True).view
        if hasattr(obj, 'name') and obj.name == name
    ]
    count = len(objects)
    if count == 1:
        return objects[0]
    elif count > 1:
        raise TooManyObjectsFound(object_type, name)
    else:
        raise NoObjectFound(object_type, name)


def wait_for_vcenter_task(task, task_description, timeout=600):
    """
    Wait for a vcenter task to finish
    :param task: A vcenter task object
    :param task_description: The task description
    :param timeout: The timeout, in seconds

    :return: The task result

    :raise: TimeoutError: If the timeout is reached
    """
    _timeout_loop(
        timeout=timeout,
        description=task_description,
        callback=lambda: task.info.state == vim.TaskInfo.State.running
    )
    if task.info.state == vim.TaskInfo.State.success:
        return task.info.result
    else:
        raise task.info.error


def wait_for_dhcp_server(vm_object, timeout=120):
    """
    Wait for the virtual machine to have an IP
    :param vm_object: A vcenter virtual machine object
    :param timeout: The timeout, in seconds

    :return: The virtual machine IP

    :raise: TimeoutError: If the timeout is reached
    """
    _timeout_loop(
        timeout=timeout,
        description='Get IP',
        callback=lambda: not vm_object.summary.guest.ipAddress
    )
    return vm_object.summary.guest.ipAddress


@contextlib.contextmanager
def ssh_context(username, password, ip):
    """
    Set the ssh context for fabric
    :param username: The ssh user
    :param password: The ssh password
    :param ip: The target machine ip
    """
    with settings(
            host_string="{}@{}".format(username, ip),
            password=password,
            warn_only=True,
            disable_known_hosts=True
    ):
        yield


def _timeout_loop(timeout, description, callback, *args, **kwargs):
    """
    Wait in a while loop for a task to complete
    :param timeout: The timeout, in seconds
    :param description: The task description
    :param callback: A function that evaluates as the while loop condition
    :param args: The positional arguments of the callback
    :param kwargs: The keyword arguments of the callback

    :raise: TimeoutError: If the timeout is reached
    """
    start = time.time()
    print('Waiting on [{}] ... '.format(description), end='')
    sys.stdout.flush()
    while callback(*args, **kwargs) and timeout:
        time.sleep(1)
        timeout -= 1
    if timeout <= 0:
        raise TimeoutError(description, timeout)
    print(datetime.timedelta(seconds=time.time() - start))
