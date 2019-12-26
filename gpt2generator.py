import os
import itertools
import torch
import torch.nn.functional as F

from transformers import GPT2LMHeadModel, GPT2Tokenizer

from getconfig import settings, logger
from story.utils import cut_trailing_sentence

DTYPE = torch.float32 if  ((not torch.cuda.is_available()) or settings.getboolean('force-cpu')) else torch.float16
logger.info('Cuda Available: {}    Force CPU: {}    DTYPE: {}'.format(torch.cuda.is_available(), settings.getboolean('force-cpu'), DTYPE))

# warnings.filterwarnings("ignore")
MODEL_CLASSES = {
    "gpt2": (GPT2LMHeadModel, GPT2Tokenizer),
}

def top_k_top_p_filtering(logits, top_k=0, top_p=0.0, filter_value=-float("Inf")):
    """ Filter a distribution of logits using top-k and/or nucleus (top-p) filtering
        Args:
            logits: logits distribution shape (batch size x vocabulary size)
            top_k > 0: keep only top k tokens with highest probability (top-k filtering).
            top_p > 0.0: keep the top tokens with cumulative probability >= top_p (nucleus filtering).
                Nucleus filtering is described in Holtzman et al. (http://arxiv.org/abs/1904.09751)
        From: https://gist.github.com/thomwolf/1a5a29f6962089e871b94cbd09daf317
    """
    top_k = min(top_k, logits.size(-1))  # Safety check
    if top_k > 0:
        # Remove all tokens with a probability less than the last token of the top-k
        indices_to_remove = logits < torch.topk(logits, top_k)[0][..., -1, None]
        logits[indices_to_remove] = filter_value

    if top_p > 0.0:
        sorted_logits, sorted_indices = torch.sort(logits, descending=True)
        cumulative_probs = torch.cumsum(F.softmax(sorted_logits, dim=-1), dim=-1)

        # Remove tokens with cumulative probability above the threshold
        sorted_indices_to_remove = cumulative_probs > top_p
        # Shift the indices to the right to keep also the first token above the threshold
        sorted_indices_to_remove[..., 1:] = sorted_indices_to_remove[..., :-1].clone()
        sorted_indices_to_remove[..., 0] = 0

        # scatter sorted tensors to original indexing
        indices_to_remove = sorted_indices_to_remove.scatter(
            dim=1, index=sorted_indices, src=sorted_indices_to_remove
        )
        logits[indices_to_remove] = filter_value
    return logits


def sample_sequence(
    model,
    length,
    context,
    num_samples=1,
    temperature=1,
    top_k=0,
    top_p=0.9,
    repetition_penalty=1.0,
    is_xlnet=False,
    is_xlm_mlm=False,
    xlm_mask_token=None,
    xlm_lang=None,
    device="cpu",
):
    context = torch.tensor(context, dtype=torch.long, device=device)
    context = context.unsqueeze(0).repeat(num_samples, 1)
    generated = context
    USE_PAST = True
    next_token = context
    outputs = None
    with torch.no_grad():
        for _ in range(length):
            if USE_PAST:
                past = outputs[1] if outputs is not None else None
                inputs = {"input_ids": next_token, 'past': past}
            else:
                inputs = {"input_ids": generated}

            outputs = model(
                **inputs
            )  # Note: we could also use 'past' with GPT-2/Transfo-XL/XLNet/CTRL (cached hidden-states)
            next_token_logits = outputs[0][:, -1, :] / (
                temperature if temperature > 0 else 1.0
            )

            # repetition penalty from CTRL (https://arxiv.org/abs/1909.05858)
            for i in range(num_samples):
                for _ in set(generated[i].tolist()):
                    next_token_logits[i, _] /= repetition_penalty

            filtered_logits = top_k_top_p_filtering(
                next_token_logits, top_k=top_k, top_p=top_p
            ).float()
            if temperature == 0:  # greedy sampling:
                next_token = torch.argmax(filtered_logits, dim=-1).unsqueeze(-1)
            else:
                next_token = torch.multinomial(
                    F.softmax(filtered_logits, dim=-1), num_samples=1
                )
            generated = torch.cat((generated, next_token), dim=1)
    return generated

def truncate_multiple_sequences(seqs, max_len=100):
    """Truncate multiple sequences, longest first, removing first."""
    while sum(len(s) for s in seqs) > max_len:
        longest = sorted(seqs, key=len, reverse=True)[0]
        longest.pop(0)

class GPT2Generator:
    def __init__(
        self, generate_num=60, temperature=0.4, top_k=40, top_p=0.9, dtype=DTYPE, censor=False, repetition_penalty=1,
    ):
        self.generate_num = generate_num
        self.temp = temperature
        self.top_k = top_k
        self.top_p = top_p
        self.censor = censor
        self.samples = 1
        self.dtype = dtype
        self.repetition_penalty = repetition_penalty
        self.batch_size = 1
        self.max_history_tokens = 1024 - generate_num
        self.stop_token = '<|endoftext|>'

        self.model_name = "pytorch-gpt2-xl-aid2-v5"
        self.model_dir = "models"
        self.checkpoint_path = os.path.join(self.model_dir, self.model_name)
        assert os.path.exists(self.checkpoint_path), "Make sure to download the pytorch v5 model and put it in " + self.checkpoint_path
        if os.environ.get("DEBUG_GPT2", False):
            self.checkpoint_path = "gpt2"
            logger.warning("using DEBUG_GPT2 MODE! This is just for devs to quickly check a small GPT2 model with poor output")
        self.device = torch.device("cuda" if self.dtype==torch.float16 else "cpu")
        logger.info("Using device={}, checkpoint={}, dtype={}".format(self.device, self.checkpoint_path, self.dtype))

        # Load tokenizer and model
        model_class, tokenizer_class = MODEL_CLASSES["gpt2"]
        self.tokenizer = tokenizer_class.from_pretrained(self.checkpoint_path)
        self.model = model_class.from_pretrained(self.checkpoint_path)
        self.model.to(self.dtype).to(self.device)
        self.model.eval()

    def sample_sequence(self, context_tokens=None, generate_num=None, temperature=None):
        generate_num = generate_num if (generate_num is not None) else self.generate_num
        temperature = temperature if (temperature is not None) else self.temp
        out = sample_sequence(
            model=self.model,
            context=context_tokens,
            length=generate_num,
            # context=self.context,
            temperature=temperature,
            top_k=self.top_k,
            top_p=self.top_p,
            repetition_penalty=self.repetition_penalty,
            num_samples=self.samples,
            device=self.device
            # batch_size=self.batch_size,
        )
        return out

    def prompt_replace(self, prompt):
        logger.debug("BEFORE PROMPT_REPLACE: `%s`", repr(prompt))
        if len(prompt) > 0 and prompt[-1] == " ":
            prompt = prompt[:-1]

        # prompt = second_to_first_person(prompt)

        # logger.debug("AFTER PROMPT_REPLACE: `%s`", repr(prompt))
        return prompt

    def result_replace(self, result):
        # logger.debug("BEFORE RESULT_REPLACE: `%s`", repr(result))

        result = cut_trailing_sentence(result)
        if len(result) == 0:
            return ""
        first_letter_capitalized = result[0].isupper()
        result = result.replace('."', '".')
        result = result.replace("#", "")
        result = result.replace("*", "")
        result = result.replace("\n\n", "\n")
        # result = first_to_second_person(result)

        if not first_letter_capitalized:
            result = result[0].lower() + result[1:]

        logger.debug("nAFTER RESULT_REPLACE: `%s`", repr(result))

        return result

    def generate_raw(self, prompt, generate_num=None, temperature=None):
        # the prompt is a list of strings, encode each one tok tokens, then truncate the longest ones
        context_tokens = [self.tokenizer.encode(p, add_special_tokens=False, max_length=self.max_history_tokens) for p in prompt]
        truncate_multiple_sequences(context_tokens, self.max_history_tokens)
        context_tokens = list(itertools.chain(*context_tokens))

        if os.environ.get("DEBUG_GPT2", False):
            logger.debug("Text passing into model %s", self.tokenizer.decode(context_tokens, clean_up_tokenization_spaces=True, skip_special_tokens=True))

        generated = 0
        for _ in range(self.samples // self.batch_size):
            out = self.sample_sequence(
                context_tokens,
                generate_num=generate_num,
                temperature=temperature
            )
            out = out[:, len(context_tokens) :].tolist()
            for o in out:
                generated += 1
                text = self.tokenizer.decode(o, clean_up_tokenization_spaces=True, skip_special_tokens=True)
                if self.stop_token:
                    index = text.find(self.stop_token)
                    if index == -1:
                        index = None
                    text = text[:index]
        return text

    def generate(self, prompt, options=None, seed=1, depth=0):

        prompt = [self.prompt_replace(p) for p in prompt]

        logger.debug("Prompt is: `%s`", repr(prompt))

        text = self.generate_raw(prompt)

        logger.debug("Generated result is: `%s`", repr(text))

        result = text
        result = self.result_replace(result)
        if len(result) == 0:
            if (depth < 20):
                logger.debug("Model generated empty text trying again %s", depth)
                return self.generate([' {}'.format(depth)] + prompt, depth=depth + 1)
            else:
                logger.warn("Model generated empty text %s times. Try another action", depth)
        return result
