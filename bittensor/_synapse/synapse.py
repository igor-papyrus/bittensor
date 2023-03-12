# The MIT License (MIT)
# Copyright © 2021 Yuma Rao

# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated 
# documentation files (the “Software”), to deal in the Software without restriction, including without limitation 
# the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, 
# and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all copies or substantial portions of 
# the Software.

# THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
# THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL 
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION 
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER 
# DEALINGS IN THE SOFTWARE.

import time
import grpc
import torch
import bittensor

from . import call

class Synapse( bittensor.grpc.BittensorServicer ):

    def __init__( self ):
        r""" Initializes a new Synapse."""
        self.priority_threadpool = bittensor.prioritythreadpool()

    def __str__(self):
        return "synapse"
    
    def _attach( self, axon: 'bittensor.axon.Axon' ):
        """ _attach: Attaches the synapse to the axon."""
        bittensor.grpc.add_BittensorServicer_to_server( self, axon.server )

    def priority( self, forward_call: call.ForwardCall ) -> float:
        raise NotImplementedError('Must implement priority() in subclass.')

    def blacklist( self, forward_call: call.ForwardCall ) -> torch.FloatTensor:
        raise NotImplementedError('Must implement blacklist() in subclass.')

    def forward(self, forward_call: call.ForwardCall ):
        raise NotImplementedError('Must implement forward() in subclass.')
        
    def _Forward( self, forward_call: call.ForwardCall ) -> 'call.ForwardCall':
        try:
            # Check blacklist.
            if self.blacklist( forward_call ): raise Exception('Blacklisted')
            # Get priority.
            priority = self.priority( forward_call )
            # Queue the forward call.
            future = self.priority_threadpool.submit(
                self.forward,
                forward_call = forward_call,
                priority = priority,
            )
        except Exception as e:
            forward_call.request_code = bittensor.proto.ReturnCode.UnknownException
            forward_call.request_message = str(e)
        finally:
            # Log request.
            bittensor.logging.rpc_log ( 
                axon = True, 
                forward = True, 
                is_response = False, 
                code = forward_call.request_code, 
                call_time = time.time() - forward_call.start_time, 
                pubkey = forward_call.hotkey, 
                uid = None, 
                inputs = forward_call.get_inputs_shape() if forward_call.request_code == bittensor.proto.ReturnCode.Success else None,
                outputs = None,
                message = forward_call.request_message,
                synapse = self.__str__()
            )
            if forward_call.request_code != bittensor.proto.ReturnCode.Success:
                return forward_call.to_forward_response_proto()

        # Do forward.
        try:
            # Get the result.
            future.result( timeout = forward_call.timeout )

        except Exception as e:
            forward_call.response_code = bittensor.proto.ReturnCode.UnknownException
            forward_call.response_message = str(e)
        finally:
            # Log response
            bittensor.logging.rpc_log ( 
                axon = True, 
                forward = True, 
                is_response = True, 
                code = forward_call.response_code, 
                call_time = time.time() - forward_call.start_time, 
                pubkey = forward_call.hotkey, 
                uid = None, 
                inputs = list( forward_call.get_inputs_shape() ) if forward_call.response_code == bittensor.proto.ReturnCode.Success else None,
                outputs = list( forward_call.get_outputs_shape() ) if forward_call.response_code == bittensor.proto.ReturnCode.Success else None,
                message = forward_call.response_message,
                synapse = self.__str__()
            )
            return forward_call.to_forward_response_proto()