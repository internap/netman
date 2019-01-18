from netman.core.objects.exceptions import BadMplsIpState


def is_valid_mpls_state(state):
    option = str(state).lower()
    if option not in ['true', 'false']:
        raise BadMplsIpState(state)
    return {'state': option == 'true'}
